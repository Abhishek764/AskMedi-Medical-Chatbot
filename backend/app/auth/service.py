"""Account lifecycle: register, login, refresh rotation, email verify, reset, delete."""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.email import EmailSender, OutgoingEmail
from app.auth.security import (
    create_access_token,
    hash_password,
    needs_rehash,
    new_opaque_token,
    token_digest,
    verify_password,
)
from app.core.config import Settings
from app.core.errors import AppError, Conflict, Unauthorized
from app.db.models import AuditLog, EmailToken, RefreshToken, User


@dataclass
class TokenPair:
    access_token: str
    refresh_token: str
    expires_in: int


def _now() -> datetime:
    return datetime.now(UTC)


def _aware(dt: datetime) -> datetime:
    """SQLite returns naive datetimes; treat them as UTC."""
    return dt if dt.tzinfo else dt.replace(tzinfo=UTC)


class AuthService:
    def __init__(self, session: AsyncSession, settings: Settings, mailer: EmailSender) -> None:
        self.s = session
        self.cfg = settings
        self.mailer = mailer

    # -- tokens ---------------------------------------------------------------
    async def _issue(self, user: User, family_id: uuid.UUID | None = None) -> TokenPair:
        refresh = new_opaque_token()
        self.s.add(
            RefreshToken(
                user_id=user.id,
                family_id=family_id or uuid.uuid4(),
                token_hash=token_digest(refresh),
                expires_at=_now() + timedelta(days=self.cfg.refresh_token_days),
            )
        )
        access = create_access_token(
            user_id=user.id,
            role=user.role.value,
            secret=self.cfg.jwt_secret,
            algorithm=self.cfg.jwt_algorithm,
            minutes=self.cfg.access_token_minutes,
        )
        return TokenPair(access, refresh, self.cfg.access_token_minutes * 60)

    # -- register / login -----------------------------------------------------
    async def register(self, email: str, password: str) -> tuple[User, TokenPair]:
        email = email.strip().lower()
        _check_password(password, self.cfg.min_password_length)
        if await self.s.scalar(select(User.id).where(User.email == email)):
            raise Conflict("An account with this email already exists.", code="email_taken")
        now = _now()
        user = User(
            email=email,
            password_hash=hash_password(password),
            age_attested_at=now,
            disclaimer_accepted_at=now,
        )
        self.s.add(user)
        await self.s.flush()
        pair = await self._issue(user)
        await self._send_token_email(user, "verify")
        self.s.add(AuditLog(actor_id=user.id, action="user.register"))
        await self.s.commit()
        return user, pair

    async def login(self, email: str, password: str) -> tuple[User, TokenPair]:
        user = await self.s.scalar(select(User).where(User.email == email.strip().lower()))
        if not verify_password(password, user.password_hash if user else None) or user is None:
            raise Unauthorized("Email or password is incorrect.", code="invalid_credentials")
        if needs_rehash(user.password_hash):
            user.password_hash = hash_password(password)  # bcrypt (v1) -> argon2id
        pair = await self._issue(user)
        await self.s.commit()
        return user, pair

    async def record_consent(self, user: User) -> None:
        now = _now()
        user.age_attested_at = now
        user.disclaimer_accepted_at = now
        self.s.add(AuditLog(actor_id=user.id, action="user.consent"))
        await self.s.commit()

    async def refresh(self, refresh_token: str) -> TokenPair:
        row = await self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_digest(refresh_token))
        )
        if row is None:
            raise Unauthorized("Session expired. Please sign in again.", code="invalid_refresh")
        if row.revoked_at is not None:
            # Reuse of a rotated token: assume theft, kill the whole family.
            await self._revoke_family(row.family_id)
            self.s.add(AuditLog(actor_id=row.user_id, action="auth.refresh_reuse_detected"))
            await self.s.commit()
            raise Unauthorized("Session expired. Please sign in again.", code="refresh_reused")
        if _aware(row.expires_at) <= _now():
            raise Unauthorized("Session expired. Please sign in again.", code="invalid_refresh")
        user = await self.s.get(User, row.user_id)
        if user is None:
            raise Unauthorized("Session expired. Please sign in again.", code="invalid_refresh")
        row.revoked_at = _now()
        pair = await self._issue(user, family_id=row.family_id)
        await self.s.commit()
        return pair

    async def logout(self, refresh_token: str) -> None:
        row = await self.s.scalar(
            select(RefreshToken).where(RefreshToken.token_hash == token_digest(refresh_token))
        )
        if row is not None:
            await self._revoke_family(row.family_id)
            await self.s.commit()

    async def _revoke_family(self, family_id: uuid.UUID) -> None:
        await self.s.execute(
            update(RefreshToken)
            .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )

    async def _revoke_all(self, user_id: uuid.UUID) -> None:
        await self.s.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=_now())
        )

    # -- email tokens ---------------------------------------------------------
    async def _send_token_email(self, user: User, purpose: str) -> None:
        token = new_opaque_token()
        ttl = timedelta(hours=24) if purpose == "verify" else timedelta(minutes=30)
        self.s.add(
            EmailToken(
                user_id=user.id,
                purpose=purpose,
                token_hash=token_digest(token),
                expires_at=_now() + ttl,
            )
        )
        subject = (
            "Verify your AskMedi email" if purpose == "verify" else "Reset your AskMedi password"
        )
        await self.mailer.send(OutgoingEmail(user.email, subject, f"token={token}"))

    async def _consume(self, token: str, purpose: str) -> EmailToken:
        row = await self.s.scalar(
            select(EmailToken).where(
                EmailToken.token_hash == token_digest(token), EmailToken.purpose == purpose
            )
        )
        if row is None or row.used_at is not None or _aware(row.expires_at) <= _now():
            raise AppError("This link is invalid or has expired.", code="invalid_token")
        row.used_at = _now()
        return row

    async def verify_email(self, token: str) -> None:
        row = await self._consume(token, "verify")
        user = await self.s.get(User, row.user_id)
        if user is not None and user.email_verified_at is None:
            user.email_verified_at = _now()
        await self.s.commit()

    async def request_password_reset(self, email: str) -> None:
        user = await self.s.scalar(select(User).where(User.email == email.strip().lower()))
        if user is not None:  # same response either way (no account enumeration)
            await self._send_token_email(user, "reset")
            await self.s.commit()

    async def reset_password(self, token: str, new_password: str) -> None:
        _check_password(new_password, self.cfg.min_password_length)
        row = await self._consume(token, "reset")
        user = await self.s.get(User, row.user_id)
        if user is None:
            raise AppError("This link is invalid or has expired.", code="invalid_token")
        user.password_hash = hash_password(new_password)
        await self._revoke_all(user.id)
        self.s.add(AuditLog(actor_id=user.id, action="user.password_reset"))
        await self.s.commit()

    # -- deletion -------------------------------------------------------------
    async def delete_account(self, user: User, password: str) -> None:
        if not verify_password(password, user.password_hash):
            raise Unauthorized("Password is incorrect.", code="invalid_credentials")
        self.s.add(AuditLog(actor_id=None, action="user.delete", target=str(user.id)))
        await self.s.delete(user)  # cascades conversations, messages, tokens, feedback
        await self.s.commit()


def _check_password(password: str, min_len: int) -> None:
    if len(password) < min_len:
        raise AppError(f"Password must be at least {min_len} characters.", code="weak_password")
    if len(set(password)) < 4:
        raise AppError("Password is too simple.", code="weak_password")
