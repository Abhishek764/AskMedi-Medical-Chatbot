"""Background worker (arq on Redis): corpus refresh and housekeeping, off the request path.

uv run arq app.worker.WorkerSettings
"""

from __future__ import annotations

import argparse
from datetime import UTC, datetime, timedelta
from typing import Any

from arq import cron
from arq.connections import RedisSettings
from sqlalchemy import delete, or_

from app.core.config import get_settings
from app.core.container import Container
from app.db.models import EmailToken, RefreshToken


async def startup(ctx: dict[str, Any]) -> None:
    container = Container(get_settings())
    await container.startup()
    ctx["container"] = container


async def shutdown(ctx: dict[str, Any]) -> None:
    await ctx["container"].shutdown()


async def purge_expired_tokens(ctx: dict[str, Any]) -> int:
    """Delete refresh/email tokens that expired or were revoked over 7 days ago."""
    now = datetime.now(UTC)
    week_ago = now - timedelta(days=7)
    async with ctx["container"].sessionmaker() as s:
        r1 = await s.execute(
            delete(RefreshToken).where(
                or_(RefreshToken.expires_at < now, RefreshToken.revoked_at < week_ago)
            )
        )
        r2 = await s.execute(delete(EmailToken).where(EmailToken.expires_at < now))
        await s.commit()
    return int(r1.rowcount or 0) + int(r2.rowcount or 0)


async def refresh_corpus(
    ctx: dict[str, Any], sources: str = "medlineplus,openfda"
) -> dict[str, object]:
    """Monthly refresh of consumer sources. Changed documents are re-chunked; unchanged
    ones are skipped by content hash. PMC additions are run by hand after eval review."""
    from app.ingest.__main__ import _run

    args = argparse.Namespace(
        sources=sources, limit=1000, papers_per_topic=0, since=2016, no_pdf=True
    )
    return (await _run(args)).as_dict()


class WorkerSettings:
    functions = [purge_expired_tokens, refresh_corpus]
    cron_jobs = [
        cron(purge_expired_tokens, hour={3}, minute={15}),
        cron(refresh_corpus, day={1}, hour={2}, minute={0}, timeout=3 * 3600),
    ]
    on_startup = startup
    on_shutdown = shutdown
    redis_settings = RedisSettings.from_dsn(get_settings().redis_url or "redis://localhost:6379")
