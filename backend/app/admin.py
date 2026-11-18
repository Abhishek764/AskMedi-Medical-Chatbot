"""Admin CLI: give an account a role (e.g. admin, to open the /admin dashboard).

    uv run python -m app.admin promote you@example.com            # -> admin
    uv run python -m app.admin promote you@example.com --role provider
    uv run python -m app.admin list                                # who has a non-public role

Runs against DATABASE_URL from .env. There is deliberately no HTTP endpoint that grants
admin: only someone with shell access to the server can do it.
"""

from __future__ import annotations

import argparse
import asyncio
import sys

from sqlalchemy import select

from app.core.config import get_settings
from app.db.models import Role, User
from app.db.session import build_engine, build_sessionmaker


async def _promote(email: str, role: Role) -> int:
    engine = build_engine(get_settings().database_url)
    try:
        async with build_sessionmaker(engine)() as s:
            user = await s.scalar(select(User).where(User.email == email.strip().lower()))
            if user is None:
                print(f"No account with email {email!r}. Sign up in the web app first.")
                return 1
            user.role = role
            await s.commit()
            print(f"{user.email} is now {role.value}. Sign out and in again to see /admin.")
            return 0
    finally:
        await engine.dispose()


async def _list() -> int:
    engine = build_engine(get_settings().database_url)
    try:
        async with build_sessionmaker(engine)() as s:
            rows = (
                await s.execute(select(User.email, User.role).where(User.role != Role.public))
            ).all()
            for email, role in rows:
                print(f"{role.value:10} {email}")
            if not rows:
                print("No admins or providers yet.")
            return 0
    finally:
        await engine.dispose()


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m app.admin")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("promote", help="set an account's role")
    p.add_argument("email")
    p.add_argument("--role", default="admin", choices=[r.value for r in Role])
    sub.add_parser("list", help="accounts with a non-public role")
    args = ap.parse_args(argv)
    if args.cmd == "promote":
        return asyncio.run(_promote(args.email, Role(args.role)))
    return asyncio.run(_list())


if __name__ == "__main__":
    sys.exit(main())
