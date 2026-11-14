import re

from sqlalchemy import update

from app.db.models import Role, User
from tests.helpers import PASSWORD, register


def _token_from_outbox(app) -> str:
    body = app.state.container.mailer.outbox[-1].body
    return re.search(r"token=(\S+)", body).group(1)


async def test_register_returns_user_and_tokens(client):
    data = await register(client, "Alice@Example.com")
    assert data["user"]["email"] == "alice@example.com"
    assert data["user"]["role"] == "public"
    assert data["user"]["email_verified"] is False
    assert data["tokens"]["refresh_token"]


async def test_register_requires_age_and_disclaimer(client):
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": PASSWORD,
            "age_confirmed": False,
            "accept_disclaimer": True,
        },
    )
    assert r.status_code == 422
    assert PASSWORD not in r.text  # validation errors never echo input


async def test_register_rejects_mass_assignment_of_role(client):
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": "a@example.com",
            "password": PASSWORD,
            "age_confirmed": True,
            "accept_disclaimer": True,
            "role": "admin",
        },
    )
    assert r.status_code == 422


async def test_duplicate_email_conflicts(client):
    await register(client, "dup@example.com")
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": "dup@example.com",
            "password": PASSWORD,
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    assert r.status_code == 409


async def test_weak_password_rejected(client):
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": "w@example.com",
            "password": "short",
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    assert r.status_code == 400
    assert r.json()["error"]["code"] == "weak_password"


async def test_login_and_me(client):
    await register(client, "bob@example.com")
    r = await client.post("/v1/auth/login", json={"email": "bob@example.com", "password": PASSWORD})
    assert r.status_code == 200
    token = r.json()["tokens"]["access_token"]
    me = await client.get("/v1/users/me", headers={"Authorization": f"Bearer {token}"})
    assert me.json()["email"] == "bob@example.com"


async def test_login_wrong_password_and_unknown_email_look_the_same(client):
    await register(client, "carol@example.com")
    a = await client.post(
        "/v1/auth/login", json={"email": "carol@example.com", "password": "nope-nope-nope"}
    )
    b = await client.post(
        "/v1/auth/login", json={"email": "ghost@example.com", "password": "nope-nope-nope"}
    )
    assert a.status_code == b.status_code == 401
    assert a.json() == b.json()


async def test_me_requires_valid_token(client):
    assert (await client.get("/v1/users/me")).status_code == 401
    r = await client.get("/v1/users/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


async def test_refresh_rotates_and_detects_reuse(client):
    data = await register(client)
    old = data["tokens"]["refresh_token"]
    r1 = await client.post("/v1/auth/refresh", json={"refresh_token": old})
    assert r1.status_code == 200
    new = r1.json()["refresh_token"]
    assert new != old
    # Replaying the rotated token revokes the whole family, including the new one.
    r2 = await client.post("/v1/auth/refresh", json={"refresh_token": old})
    assert r2.status_code == 401 and r2.json()["error"]["code"] == "refresh_reused"
    r3 = await client.post("/v1/auth/refresh", json={"refresh_token": new})
    assert r3.status_code == 401


async def test_refresh_via_cookie(client):
    await register(client)
    assert client.cookies.get("askmedi_refresh")
    r = await client.post("/v1/auth/refresh")
    assert r.status_code == 200


async def test_logout_revokes_refresh(client):
    data = await register(client)
    token = data["tokens"]["refresh_token"]
    assert (await client.post("/v1/auth/logout", json={"refresh_token": token})).status_code == 204
    assert (await client.post("/v1/auth/refresh", json={"refresh_token": token})).status_code == 401


async def test_verify_email_flow(app, client):
    data = await register(client)
    token = _token_from_outbox(app)
    assert (await client.post("/v1/auth/verify-email", json={"token": token})).status_code == 204
    me = await client.get("/v1/users/me", headers=data["auth"])
    assert me.json()["email_verified"] is True
    again = await client.post("/v1/auth/verify-email", json={"token": token})
    assert again.status_code == 400  # one-time use


async def test_password_reset_flow_revokes_sessions(app, client):
    data = await register(client, "reset@example.com")
    r = await client.post("/v1/auth/request-password-reset", json={"email": "reset@example.com"})
    assert r.status_code == 202
    unknown = await client.post("/v1/auth/request-password-reset", json={"email": "no@example.com"})
    assert unknown.json() == r.json()
    token = _token_from_outbox(app)
    r = await client.post(
        "/v1/auth/reset-password", json={"token": token, "new_password": "a-brand-new-password"}
    )
    assert r.status_code == 204
    old_refresh = data["tokens"]["refresh_token"]
    assert (
        await client.post("/v1/auth/refresh", json={"refresh_token": old_refresh})
    ).status_code == 401
    login = await client.post(
        "/v1/auth/login", json={"email": "reset@example.com", "password": "a-brand-new-password"}
    )
    assert login.status_code == 200


async def test_delete_account(client):
    data = await register(client, "gone@example.com")
    bad = await client.request(
        "DELETE", "/v1/users/me", json={"password": "wrong-password"}, headers=data["auth"]
    )
    assert bad.status_code == 401
    ok = await client.request(
        "DELETE", "/v1/users/me", json={"password": PASSWORD}, headers=data["auth"]
    )
    assert ok.status_code == 204
    assert (await client.get("/v1/users/me", headers=data["auth"])).status_code == 401


async def test_export_contains_user(client):
    data = await register(client)
    r = await client.get("/v1/users/me/export", headers=data["auth"])
    assert r.json()["user"]["email"] == data["email"]


async def test_auth_rate_limit(app, client):
    app.state.container.settings.auth_rate_limit_per_minute = 3
    codes = [
        (
            await client.post(
                "/v1/auth/login", json={"email": "x@example.com", "password": "pw-pw-pw-pw"}
            )
        ).status_code
        for _ in range(5)
    ]
    assert codes[:3] == [401, 401, 401]
    assert codes[3:] == [429, 429]


async def test_provider_verification_and_admin_review(app, client):
    user = await register(client)
    admin = await register(client)
    r = await client.post(
        "/v1/provider-verifications",
        json={"profession": "pharmacist", "registration_number": "PCI-12345", "council": "PCI"},
        headers=user["auth"],
    )
    assert r.status_code == 201
    vid = r.json()["id"]
    # A normal user cannot review.
    denied = await client.post(
        f"/v1/admin/provider-verifications/{vid}/review",
        json={"decision": "approved"},
        headers=user["auth"],
    )
    assert denied.status_code == 403
    async with app.state.container.sessionmaker() as s:
        await s.execute(update(User).where(User.email == admin["email"]).values(role=Role.admin))
        await s.commit()
    pending = await client.get("/v1/admin/provider-verifications", headers=admin["auth"])
    assert [p["id"] for p in pending.json()] == [vid]
    ok = await client.post(
        f"/v1/admin/provider-verifications/{vid}/review",
        json={"decision": "approved"},
        headers=admin["auth"],
    )
    assert ok.json()["status"] == "approved"
    me = await client.get("/v1/users/me", headers=user["auth"])
    assert me.json()["role"] == "provider"
