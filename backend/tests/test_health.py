import pytest

from app.core.config import Settings
from app.core.kv import InMemoryKV


async def test_healthz(client):
    r = await client.get("/healthz")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}
    assert r.headers["X-Content-Type-Options"] == "nosniff"
    assert r.headers["X-Request-ID"]


async def test_readyz_checks_dependencies(client):
    r = await client.get("/readyz")
    assert r.status_code == 200
    assert r.json()["checks"] == {"database": True, "kv": True, "vector_store": True}


def test_prod_rejects_dev_secret():
    with pytest.raises(ValueError, match="JWT_SECRET"):
        Settings(
            _env_file=None,
            env="prod",
            redis_url="redis://x",
            database_url="postgresql+asyncpg://x/y",
        )


def test_paid_provider_requires_key():
    with pytest.raises(ValueError, match="OPENAI_API_KEY"):
        Settings(_env_file=None, env="test", llm_provider="openai")


async def test_inmemory_kv_ttl_and_incr():
    now = [0.0]
    kv = InMemoryKV(clock=lambda: now[0])
    assert await kv.incr("k", ttl_seconds=10) == 1
    assert await kv.incr("k", ttl_seconds=10) == 2
    now[0] = 11
    assert await kv.get("k") is None
    assert await kv.incr("k", ttl_seconds=10) == 1


async def test_readyz_reports_free_mode_without_keys(client):
    r = await client.get("/readyz")
    assert r.json()["llm"] == {"models": [], "fallback": "extractive"}
