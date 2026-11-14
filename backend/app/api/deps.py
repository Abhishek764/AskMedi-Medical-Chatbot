"""Request-scoped dependencies: DB session, current user, roles, rate limits."""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator, Callable, Coroutine
from typing import Annotated, Any

from fastapi import Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.security import decode_access_token
from app.core.config import Settings
from app.core.container import Container
from app.core.errors import Forbidden, Unauthorized
from app.core.ratelimit import enforce_limit
from app.db.models import Role, User


def get_container(request: Request) -> Container:
    return request.app.state.container  # type: ignore[no-any-return]


def get_settings_dep(request: Request) -> Settings:
    return request.app.state.settings  # type: ignore[no-any-return]


async def get_session(
    container: Annotated[Container, Depends(get_container)],
) -> AsyncIterator[AsyncSession]:
    async with container.sessionmaker() as session:
        yield session


SessionDep = Annotated[AsyncSession, Depends(get_session)]
ContainerDep = Annotated[Container, Depends(get_container)]
SettingsDep = Annotated[Settings, Depends(get_settings_dep)]


def client_ip(request: Request) -> str:
    # Behind Cloudflare the real client IP is in CF-Connecting-IP; trust it only there.
    return request.headers.get("CF-Connecting-IP") or (
        request.client.host if request.client else "unknown"
    )


async def current_user(request: Request, session: SessionDep, settings: SettingsDep) -> User:
    header = request.headers.get("Authorization", "")
    scheme, _, token = header.partition(" ")
    if scheme.lower() != "bearer" or not token:
        raise Unauthorized("Sign in required.")
    claims = decode_access_token(
        token, secret=settings.jwt_secret, algorithm=settings.jwt_algorithm
    )
    if claims is None:
        raise Unauthorized("Session expired. Please sign in again.", code="invalid_token")
    try:
        user_id = uuid.UUID(str(claims["sub"]))
    except ValueError as exc:
        raise Unauthorized("Invalid token.", code="invalid_token") from exc
    user = await session.get(User, user_id)
    if user is None:
        raise Unauthorized("Account not found.", code="invalid_token")
    return user


CurrentUser = Annotated[User, Depends(current_user)]


def require_role(*roles: Role) -> Callable[[User], Coroutine[Any, Any, User]]:
    async def _check(user: CurrentUser) -> User:
        if user.role not in roles:
            raise Forbidden("You don't have access to this.")
        return user

    return _check


def ip_rate_limit(bucket: str, per_minute_attr: str) -> Callable[..., Coroutine[Any, Any, None]]:
    async def _limit(request: Request, container: ContainerDep, settings: SettingsDep) -> None:
        limit = int(getattr(settings, per_minute_attr))
        await enforce_limit(container.kv, f"{bucket}:ip:{client_ip(request)}", limit, 60)

    return _limit
