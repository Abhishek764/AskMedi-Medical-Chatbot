"""Prometheus endpoint protection and the admin CLI."""

import httpx
import pytest
from asgi_lifespan import LifespanManager
from sqlalchemy import select

from app import admin
from app.core.config import Settings
from app.db.models import Role, User
from app.main import create_app


async def _get_metrics(settings: Settings, headers: dict[str, str] | None = None) -> int:
    app = create_app(settings)
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as c:
            return (await c.get("/metrics", headers=headers or {})).status_code


@pytest.mark.parametrize(
    ("token", "header", "status"),
    [
        (None, None, 404),  # outside dev with no token: disabled
        ("s3cret-token", None, 404),
        ("s3cret-token", "Bearer wrong", 404),
        ("s3cret-token", "Bearer s3cret-token", 200),
    ],
)
async def test_metrics_need_a_token_outside_dev(settings, token, header, status, monkeypatch):
    # staging validation needs Postgres/Redis; bypass it by setting env after construction
    s = settings.model_copy(update={"metrics_token": token})
    object.__setattr__(s, "env", "staging")
    headers = {"Authorization": header} if header else None
    assert await _get_metrics(s, headers) == status


async def test_promote_cli(app, client, settings, monkeypatch, capsys):
    email = "promote-me@example.com"
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": "a-long-password-1",
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    assert r.status_code == 201
    monkeypatch.setattr(admin, "get_settings", lambda: settings)
    assert await admin._promote("Promote-Me@example.com ", Role.admin) == 0
    assert await admin._promote("nobody@example.com", Role.admin) == 1
    async with app.state.container.sessionmaker() as s:
        assert (await s.scalar(select(User.role).where(User.email == email))) == Role.admin
