from __future__ import annotations

import itertools

_counter = itertools.count()
PASSWORD = "correct-horse-battery-1"


async def register(client, email: str | None = None, password: str = PASSWORD) -> dict:
    email = email or f"user{next(_counter)}@example.com"
    r = await client.post(
        "/v1/auth/register",
        json={
            "email": email,
            "password": password,
            "age_confirmed": True,
            "accept_disclaimer": True,
        },
    )
    assert r.status_code == 201, r.text
    data = r.json()
    data["auth"] = {"Authorization": f"Bearer {data['tokens']['access_token']}"}
    data["email"] = email
    return data
