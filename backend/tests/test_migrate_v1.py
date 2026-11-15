import bcrypt
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

from app.db.models import User
from app.migrate_v1 import migrate, v1_uuid


async def _make_v1_db(path) -> str:
    url = f"sqlite+aiosqlite:///{path}"
    eng = create_async_engine(url)
    pw = bcrypt.hashpw(b"old-v1-password", bcrypt.gensalt()).decode()
    async with eng.begin() as c:
        for ddl in [
            "CREATE TABLE users (id INTEGER PRIMARY KEY, email TEXT, password_hash TEXT, created_at TIMESTAMP)",
            "CREATE TABLE conversations (id INTEGER PRIMARY KEY, user_id INTEGER, title TEXT, created_at TIMESTAMP)",
            "CREATE TABLE messages (id INTEGER PRIMARY KEY, conversation_id INTEGER, role TEXT, content TEXT, created_at TIMESTAMP)",
        ]:
            await c.execute(text(ddl))
        await c.execute(
            text(
                "INSERT INTO users VALUES (1, 'Old@Example.com', :pw, '2026-06-01 10:00:00')"
            ).bindparams(pw=pw)
        )
        await c.execute(
            text("INSERT INTO conversations VALUES (7, 1, 'Asthma chat', '2026-06-01 10:01:00')")
        )
        await c.execute(
            text(
                "INSERT INTO messages VALUES (1, 7, 'user', 'What is asthma?', '2026-06-01 10:01:00')"
            )
        )
        await c.execute(
            text(
                "INSERT INTO messages VALUES (2, 7, 'assistant', 'Asthma is...', '2026-06-01 10:01:05')"
            )
        )
    await eng.dispose()
    return url


async def test_migrates_users_chats_and_upgrades_password(app, client, tmp_path):
    src = await _make_v1_db(tmp_path / "v1.db")
    sm = app.state.container.sessionmaker

    r1 = await migrate(src, sm)
    assert (r1.users, r1.conversations, r1.messages) == (1, 1, 2)
    r2 = await migrate(src, sm)  # idempotent
    assert (r2.users, r2.conversations, r2.messages) == (0, 0, 0)

    login = await client.post(
        "/v1/auth/login", json={"email": "old@example.com", "password": "old-v1-password"}
    )
    assert login.status_code == 200
    body = login.json()
    assert body["user"]["consent_required"] is True
    auth = {"Authorization": f"Bearer {body['tokens']['access_token']}"}

    async with sm() as s:
        user = await s.get(User, v1_uuid("user", 1))
        assert user.password_hash.startswith("$argon2")  # rehashed on login

    convs = (await client.get("/v1/conversations", headers=auth)).json()
    assert convs[0]["title"] == "Asthma chat"
    detail = (await client.get(f"/v1/conversations/{convs[0]['id']}", headers=auth)).json()
    assert [m["role"] for m in detail["messages"]] == ["user", "assistant"]

    blocked = await client.post(
        f"/v1/conversations/{convs[0]['id']}/messages",
        json={"question": "What is asthma?"},
        headers=auth,
    )
    assert blocked.status_code == 403 and blocked.json()["error"]["code"] == "consent_required"

    ok = await client.post(
        "/v1/users/me/consent",
        json={"age_confirmed": True, "accept_disclaimer": True},
        headers=auth,
    )
    assert ok.json()["consent_required"] is False
    after = await client.post(
        f"/v1/conversations/{convs[0]['id']}/messages",
        json={"question": "What is asthma?"},
        headers=auth,
    )
    assert after.status_code == 200


async def test_dry_run_writes_nothing(app, tmp_path):
    src = await _make_v1_db(tmp_path / "v1.db")
    r = await migrate(src, app.state.container.sessionmaker, dry_run=True)
    assert r.users == 1
    async with app.state.container.sessionmaker() as s:
        assert await s.get(User, v1_uuid("user", 1)) is None
