"""Password hashing (argon2id), JWT access tokens, opaque refresh/email tokens."""

from __future__ import annotations

import hashlib
import secrets
import uuid
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

_hasher = PasswordHasher()
# Used when the email is unknown so login timing does not reveal which accounts exist.
_DUMMY_HASH = _hasher.hash("timing-equaliser-not-a-real-password")


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password: str, password_hash: str | None) -> bool:
    try:
        return _hasher.verify(password_hash or _DUMMY_HASH, password) and password_hash is not None
    except (VerifyMismatchError, InvalidHashError):
        return False


def create_access_token(
    *, user_id: uuid.UUID, role: str, secret: str, algorithm: str, minutes: int
) -> str:
    now = datetime.now(UTC)
    claims = {
        "sub": str(user_id),
        "role": role,
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, secret, algorithm=algorithm)


def decode_access_token(token: str, *, secret: str, algorithm: str) -> dict[str, object] | None:
    try:
        claims = jwt.decode(
            token, secret, algorithms=[algorithm], options={"require": ["exp", "sub", "type"]}
        )
    except jwt.PyJWTError:
        return None
    return claims if claims.get("type") == "access" else None


def new_opaque_token() -> str:
    return secrets.token_urlsafe(32)


def token_digest(token: str) -> str:
    """Opaque tokens are high-entropy, so a fast hash is enough for storage."""
    return hashlib.sha256(token.encode()).hexdigest()
