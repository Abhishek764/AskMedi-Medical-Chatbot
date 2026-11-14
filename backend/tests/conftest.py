from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
def settings(tmp_path) -> Settings:
    return Settings(
        _env_file=None,
        env="test",
        embeddings_provider="hash",
        rerank_provider="none",
        llm_provider="extractive",
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        qdrant_path=str(tmp_path / "qdrant"),
        redis_url=None,
    )


@pytest.fixture
async def app(settings: Settings):
    application = create_app(settings)
    async with LifespanManager(application):
        yield application


@pytest.fixture
async def client(app) -> AsyncIterator[httpx.AsyncClient]:
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
