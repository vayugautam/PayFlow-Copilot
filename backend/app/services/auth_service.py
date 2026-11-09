"""Authentication-related persistence services."""

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import get_password_hash, verify_password
from app.models import User


class DuplicateEmailError(Exception):
    """Raised when an email is already registered."""


def normalize_email(email: str) -> str:
    return email.strip().lower()


async def register_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User:
    """Create and persist a user with an Argon2id password hash."""
    normalized_email = normalize_email(email)
    existing = await db.scalar(select(User).where(User.email == normalized_email))
    if existing is not None:
        raise DuplicateEmailError

    user = User(
        email=normalized_email,
        password_hash=get_password_hash(password),
    )
    db.add(user)
    try:
        await db.commit()
        await db.refresh(user)
    except IntegrityError as exc:
        await db.rollback()
        raise DuplicateEmailError from exc
    return user


async def authenticate_user(
    db: AsyncSession,
    email: str,
    password: str,
) -> User | None:
    """Return an active user for valid credentials, otherwise None."""
    normalized_email = normalize_email(email)
    user = await db.scalar(select(User).where(User.email == normalized_email))
    if user is None or not user.is_active:
        return None
    if not verify_password(password, user.password_hash):
        return None
    return user
