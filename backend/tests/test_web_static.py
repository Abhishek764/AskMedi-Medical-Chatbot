"""Serving the built web app from the API process (single-origin free hosting)."""

import httpx
import pytest
from asgi_lifespan import LifespanManager

from app.core.config import Settings
from app.main import create_app


@pytest.fixture
async def web_client(settings: Settings, tmp_path):
    dist = tmp_path / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<html>app</html>")
    (dist / "assets" / "app-1a2b.js").write_text("console.log(1)")
    (tmp_path / "secret.txt").write_text("nope")
    app = create_app(settings.model_copy(update={"web_dist_dir": str(dist)}))
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


async def test_index_and_spa_fallback(web_client):
    for path in ("/", "/admin", "/c/123"):
        r = await web_client.get(path)
        assert r.status_code == 200
        assert "app" in r.text


async def test_hashed_assets_are_cached(web_client):
    r = await web_client.get("/assets/app-1a2b.js")
    assert r.status_code == 200
    assert "immutable" in r.headers["Cache-Control"]


async def test_api_routes_win_and_unknown_api_is_404(web_client):
    assert (await web_client.get("/healthz")).json() == {"status": "ok"}
    assert (await web_client.get("/v1/nope")).status_code == 404


async def test_no_path_traversal(web_client):
    r = await web_client.get("/..%2Fsecret.txt")
    assert "nope" not in r.text


def test_prod_allows_inprocess_kv_only_when_opted_in():
    base = dict(
        _env_file=None,
        env="prod",
        jwt_secret="x" * 40,
        database_url="postgresql+asyncpg://x/y",
        db_auto_create=False,
    )
    with pytest.raises(ValueError, match="REDIS_URL"):
        Settings(**base)
    assert Settings(**base, allow_inprocess_kv=True).redis_url is None
