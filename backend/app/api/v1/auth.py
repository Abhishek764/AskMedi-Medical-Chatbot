"""Auth endpoints. Mobile uses the refresh token from the body; web uses an httpOnly cookie."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Cookie, Depends, Response, status

from app.api.deps import ContainerDep, SessionDep, SettingsDep, ip_rate_limit
from app.api.v1.schemas import (
    AuthOut,
    LoginIn,
    RefreshIn,
    RegisterIn,
    ResetPasswordIn,
    ResetRequestIn,
    TokenOut,
    UserOut,
    VerifyEmailIn,
)
from app.auth.service import AuthService, TokenPair
from app.core.config import Settings
from app.core.errors import Unauthorized
from app.db.models import User

REFRESH_COOKIE = "askmedi_refresh"

router = APIRouter(
    prefix="/auth",
    tags=["auth"],
    dependencies=[Depends(ip_rate_limit("auth", "auth_rate_limit_per_minute"))],
)


def user_out(user: User) -> UserOut:
    return UserOut(
        id=user.id,
        email=user.email,
        role=user.role.value,
        email_verified=user.email_verified_at is not None,
        consent_required=user.age_attested_at is None or user.disclaimer_accepted_at is None,
        created_at=user.created_at,
    )


def _tokens(pair: TokenPair, response: Response, settings: Settings) -> TokenOut:
    response.set_cookie(
        REFRESH_COOKIE,
        pair.refresh_token,
        max_age=settings.refresh_token_days * 86400,
        httponly=True,
        secure=settings.env in ("staging", "prod"),
        samesite="strict",
        path="/v1/auth",
    )
    return TokenOut(
        access_token=pair.access_token, refresh_token=pair.refresh_token, expires_in=pair.expires_in
    )


def _service(session: SessionDep, settings: SettingsDep, container: ContainerDep) -> AuthService:
    return AuthService(session, settings, container.mailer)


ServiceDep = Annotated[AuthService, Depends(_service)]


@router.post("/register", response_model=AuthOut, status_code=status.HTTP_201_CREATED)
async def register(body: RegisterIn, svc: ServiceDep, response: Response, settings: SettingsDep):
    user, pair = await svc.register(body.email, body.password)
    return AuthOut(user=user_out(user), tokens=_tokens(pair, response, settings))


@router.post("/login", response_model=AuthOut)
async def login(body: LoginIn, svc: ServiceDep, response: Response, settings: SettingsDep):
    user, pair = await svc.login(body.email, body.password)
    return AuthOut(user=user_out(user), tokens=_tokens(pair, response, settings))


@router.post("/refresh", response_model=TokenOut)
async def refresh(
    svc: ServiceDep,
    response: Response,
    settings: SettingsDep,
    body: RefreshIn | None = None,
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
):
    token = (body.refresh_token if body else None) or cookie_token
    if not token:
        raise Unauthorized("Session expired. Please sign in again.", code="invalid_refresh")
    return _tokens(await svc.refresh(token), response, settings)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    svc: ServiceDep,
    response: Response,
    body: RefreshIn | None = None,
    cookie_token: Annotated[str | None, Cookie(alias=REFRESH_COOKIE)] = None,
) -> Response:
    token = (body.refresh_token if body else None) or cookie_token
    if token:
        await svc.logout(token)
    response.delete_cookie(REFRESH_COOKIE, path="/v1/auth")
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/verify-email", status_code=status.HTTP_204_NO_CONTENT)
async def verify_email(body: VerifyEmailIn, svc: ServiceDep) -> None:
    await svc.verify_email(body.token)


@router.post("/request-password-reset", status_code=status.HTTP_202_ACCEPTED)
async def request_password_reset(body: ResetRequestIn, svc: ServiceDep) -> dict[str, str]:
    await svc.request_password_reset(body.email)
    return {"status": "If that account exists, we sent a reset link."}


@router.post("/reset-password", status_code=status.HTTP_204_NO_CONTENT)
async def reset_password(body: ResetPasswordIn, svc: ServiceDep) -> None:
    await svc.reset_password(body.token, body.new_password)
