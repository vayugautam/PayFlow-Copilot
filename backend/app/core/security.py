"""Reusable password hashing and JWT security utilities."""

from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import UUID

import jwt
from jwt.exceptions import InvalidTokenError
from pwdlib import PasswordHash
from pwdlib.exceptions import UnknownHashError

from app.core.config import get_settings

password_hash = PasswordHash.recommended()


def get_password_hash(password: str) -> str:
    """Return an Argon2id hash for a plaintext password."""
    return password_hash.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Return whether a plaintext password matches a stored hash."""
    try:
        return password_hash.verify(plain_password, hashed_password)
    except (TypeError, ValueError, UnknownHashError):
        return False


def create_access_token(
    subject: str | UUID,
    expires_delta: timedelta | None = None,
) -> str:
    """Create a signed JWT containing only the required authentication claims."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    expires_at = now + (
        expires_delta
        if expires_delta is not None
        else timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    payload = {
        "sub": str(subject),
        "iat": now,
        "exp": expires_at,
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_access_token(token: str) -> dict[str, Any]:
    """Verify and decode a JWT access token with required claims."""
    settings = get_settings()
    payload = jwt.decode(
        token,
        settings.SECRET_KEY,
        algorithms=[settings.ALGORITHM],
        options={"require": ["sub", "iat", "exp"]},
    )
    subject = payload.get("sub")
    if not isinstance(subject, str) or not subject:
        raise InvalidTokenError("Token subject must be a non-empty string")
    return payload