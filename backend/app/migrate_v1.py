"""Copy users, conversations and messages from the v1 (Flask) database into v2.

    uv run python -m app.migrate_v1 --source "postgresql+asyncpg://user:pass@host/v1db"
    uv run python -m app.migrate_v1 --source "sqlite+aiosqlite:///../instance/askmedi.db" --dry-run

- v1 integer ids become deterministic UUIDs, so re-running is safe (existing rows are skipped).
- bcrypt password hashes are kept; they are upgraded to argon2id on each user's next login.
- Migrated users have no age/disclaimer record, so they must confirm both before chatting.
- v1 answers had no citations or safety checks: they are imported with status "complete" and
  model "v1" so analytics can tell them apart.
"""

from __future__ import annotations

import argparse
import asyncio
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.db.models import AuditLog, Conversation, Message, MessageStatus, User

_NS = uuid.UUID("0b7d6b43-6f5f-4c55-9a0a-3b1f2e9c7d21")


def v1_uuid(kind: str, v1_id: int) -> uuid.UUID:
    return uuid.uuid5(_NS, f"v1-{kind}-{v1_id}")


def _ts(value: object) -> datetime:
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=UTC)
    if isinstance(value, str) and value:
        dt = datetime.fromisoformat(value)
        return dt if dt.tzinfo else dt.replace(tzinfo=UTC)
    return datetime.now(UTC)


@dataclass
class MigrationReport:
    users: int = 0
    users_skipped: int = 0
    conversations: int = 0
    messages: int = 0


async def migrate(
    source_url: str, target: async_sessionmaker[AsyncSession], *, dry_run: bool = False
) -> MigrationReport:
    report = MigrationReport()
    src = create_async_engine(source_url)
    try:
        async with src.connect() as conn:
            users = (
                await conn.execute(
                    text("SELECT id, email, password_hash, created_at FROM users ORDER BY id")
                )
            ).all()
            convs = (
                await conn.execute(
                    text("SELECT id, user_id, title, created_at FROM conversations ORDER BY id")
                )
            ).all()
            msgs = (
                await conn.execute(
                    text(
                        "SELECT id, conversation_id, role, content, created_at FROM messages ORDER BY id"
                    )
                )
            ).all()
    finally:
        await src.dispose()

    async with target() as s:
        known_users: set[uuid.UUID] = set()
        for uid, email, pw_hash, created in users:
            new_id = v1_uuid("user", uid)
            email_n = str(email).strip().lower()
            exists = await s.get(User, new_id)
            taken = await s.scalar(
                text("SELECT 1 FROM users WHERE email = :e").bindparams(e=email_n)
            )
            if exists or taken:
                report.users_skipped += 1
                if exists:
                    known_users.add(new_id)
                continue
            s.add(
                User(
                    id=new_id,
                    email=email_n,
                    password_hash=str(pw_hash),
                    created_at=_ts(created),
                    age_attested_at=None,
                    disclaimer_accepted_at=None,
                )
            )
            known_users.add(new_id)
            report.users += 1
        await s.flush()

        known_convs: set[uuid.UUID] = set()
        for cid, uid, title, created in convs:
            new_id, owner = v1_uuid("conversation", cid), v1_uuid("user", uid)
            if owner not in known_users:
                continue
            known_convs.add(new_id)
            if await s.get(Conversation, new_id):
                continue
            s.add(
                Conversation(
                    id=new_id,
                    user_id=owner,
                    title=(title or "New chat")[:200],
                    created_at=_ts(created),
                    updated_at=_ts(created),
                )
            )
            report.conversations += 1
        await s.flush()

        for mid, cid, role, content, created in msgs:
            new_id, conv = v1_uuid("message", mid), v1_uuid("conversation", cid)
            if conv not in known_convs or await s.get(Message, new_id):
                continue
            s.add(
                Message(
                    id=new_id,
                    conversation_id=conv,
                    role="assistant" if role == "assistant" else "user",
                    content=str(content),
                    status=MessageStatus.complete,
                    model="v1" if role == "assistant" else None,
                    created_at=_ts(created),
                )
            )
            report.messages += 1

        s.add(AuditLog(action="migrate.v1", details=report.__dict__.copy()))
        if dry_run:
            await s.rollback()
        else:
            await s.commit()
    return report


async def _main(args: argparse.Namespace) -> None:
    from app.core.config import get_settings
    from app.core.container import Container

    container = Container(get_settings())
    await container.startup()
    try:
        report = await migrate(args.source, container.sessionmaker, dry_run=args.dry_run)
        print(("DRY RUN " if args.dry_run else "") + str(report))
    finally:
        await container.shutdown()


if __name__ == "__main__":
    ap = argparse.ArgumentParser(prog="python -m app.migrate_v1")
    ap.add_argument("--source", required=True, help="async SQLAlchemy URL of the v1 database")
    ap.add_argument("--dry-run", action="store_true")
    asyncio.run(_main(ap.parse_args()))
