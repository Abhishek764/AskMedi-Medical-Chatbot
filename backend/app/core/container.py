"""Process-wide dependencies, built once at startup and torn down at shutdown."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from app.auth.email import OutboxEmailSender
from app.core.config import Settings
from app.core.kv import KV, build_kv
from app.db.session import build_engine, build_sessionmaker


class Container:
    def __init__(self, settings: Settings) -> None:
        self.settings = settings
        self.engine: AsyncEngine = build_engine(settings.database_url)
        self.sessionmaker: async_sessionmaker[AsyncSession] = build_sessionmaker(self.engine)
        self.kv: KV = build_kv(settings.redis_url)
        self.mailer = OutboxEmailSender(echo_body=settings.env == "dev")

    async def startup(self) -> None:
        if self.settings.db_auto_create:
            # dev/test convenience; staging/prod run `alembic upgrade head` before deploy
            from app.db.models import Base

            async with self.engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)

    async def shutdown(self) -> None:
        await self.kv.close()
        await self.engine.dispose()
