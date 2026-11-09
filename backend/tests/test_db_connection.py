"""Unit and integration tests for Settings, SQLAlchemy 2.0 Base, and async DB session.

Test organisation:
  - Synchronous unit tests (no DB required): Settings, Base, TimestampMixin,
    engine/session factory configuration.
  - Integration tests (require a live PostgreSQL): marked @pytest.mark.integration
    and auto-skipped when no database is reachable.
"""

import inspect
import os
import socket
from urllib.parse import urlparse

import pytest
from sqlalchemy import Integer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from app.core.config import Settings, get_settings
from app.db.base import Base, TimestampMixin
from app.db.session import AsyncSessionLocal, engine, get_db


# ---------------------------------------------------------------------------
# Helper: check DB reachability with a 1-second TCP probe (never blocks tests)
# ---------------------------------------------------------------------------

def _test_database_url() -> str | None:
    """Return the explicitly configured integration-test database URL."""
    return os.environ.get("TEST_DATABASE_URL")


def _is_db_reachable() -> bool:
    """Return True if the configured test DB host/port responds within 1 s."""
    database_url = _test_database_url()
    if not database_url:
        return False

    parsed = urlparse(database_url)
    host = parsed.hostname or "localhost"
    port = parsed.port or 5432
    try:
        with socket.create_connection((host, port), timeout=1):
            return True
    except OSError:
        return False


def _integration_skip_reason() -> str:
    database_url = _test_database_url()
    if not database_url:
        return "TEST_DATABASE_URL is not configured — skipping integration test"
    if urlparse(database_url).path.lstrip("/") == "payflow_copilot":
        return "TEST_DATABASE_URL must target a separate test database — skipping integration test"
    if not _is_db_reachable():
        return "TEST_DATABASE_URL host is not reachable — skipping integration test"
    return ""


db_available = pytest.mark.skipif(
    _integration_skip_reason() != "",
    reason=_integration_skip_reason(),
)


# ---------------------------------------------------------------------------
# Settings — synchronous unit tests (no DB required)
# ---------------------------------------------------------------------------

def test_settings_defaults():
    """Default settings values load correctly from .env."""
    settings = get_settings()

    assert settings.APP_NAME == "PayFlow Copilot"
    assert settings.ALGORITHM == "HS256"
    assert settings.ACCESS_TOKEN_EXPIRE_MINUTES > 0
    assert "postgresql+psycopg://" in settings.DATABASE_URL
    assert isinstance(settings.CORS_ORIGINS, list)


def test_settings_secret_masking():
    """Sensitive values must never appear in repr() or str() output."""
    settings = get_settings()

    r = repr(settings)
    s = str(settings)

    assert settings.SECRET_KEY not in r
    assert "SECRET_KEY='***'" in r
    assert settings.SECRET_KEY not in s
    assert settings.masked_database_url is not None


def test_cors_origins_comma_string():
    """CORS_ORIGINS parses a bare comma-separated string correctly."""
    s = Settings(CORS_ORIGINS="http://localhost:3000,http://localhost:8000")
    assert s.CORS_ORIGINS == ["http://localhost:3000", "http://localhost:8000"]


def test_cors_origins_json_array():
    """CORS_ORIGINS parses a JSON array string correctly."""
    s = Settings(CORS_ORIGINS='["http://example.com", "http://app.com"]')
    assert s.CORS_ORIGINS == ["http://example.com", "http://app.com"]


def test_cors_origins_empty_string():
    """An empty CORS_ORIGINS value must not raise — it must return an empty list."""
    s = Settings(CORS_ORIGINS="")
    assert s.CORS_ORIGINS == []


def test_cors_origins_default_is_list():
    """The loaded CORS_ORIGINS is always a list."""
    s = get_settings()
    assert isinstance(s.CORS_ORIGINS, list)


def test_production_debug_true_raises():
    """DEBUG=True in production must raise ValueError."""
    with pytest.raises(ValueError, match="DEBUG must be False in production"):
        Settings(APP_ENV="production", DEBUG=True, SECRET_KEY="a" * 32)


def test_production_weak_secret_raises():
    """A short SECRET_KEY in production must raise ValueError."""
    with pytest.raises(ValueError, match="SECRET_KEY must be a cryptographically secure key"):
        Settings(APP_ENV="production", DEBUG=False, SECRET_KEY="too-short")


# ---------------------------------------------------------------------------
# ORM Base and TimestampMixin — synchronous unit tests (no DB required)
# ---------------------------------------------------------------------------

def test_declarative_base_is_correct_type():
    """Base must be a subclass of SQLAlchemy's DeclarativeBase."""
    assert issubclass(Base, DeclarativeBase)


def test_timestamp_mixin_adds_tz_aware_columns():
    """TimestampMixin must add timezone-aware created_at and updated_at columns."""

    class _Probe(Base, TimestampMixin):
        __tablename__ = "probe_for_mixin_test"
        id: Mapped[int] = mapped_column(Integer, primary_key=True)

    tbl = _Probe.__table__
    assert "created_at" in tbl.c
    assert "updated_at" in tbl.c
    assert tbl.c.created_at.type.timezone is True
    assert tbl.c.updated_at.type.timezone is True


# ---------------------------------------------------------------------------
# Session factory — synchronous unit tests (no DB connection opened)
# ---------------------------------------------------------------------------

def test_engine_uses_postgresql_dialect():
    """The async engine must be configured for PostgreSQL."""
    assert engine is not None
    assert engine.dialect.name == "postgresql"


def test_async_session_local_instantiates_async_session():
    """Calling AsyncSessionLocal() returns an AsyncSession without connecting to the DB.

    async_sessionmaker.__call__ constructs the session object in memory;
    it does NOT open a connection until the first await inside the session.
    """
    session = AsyncSessionLocal()
    assert isinstance(session, AsyncSession)
    # No await — we only confirm the returned type, no I/O is performed.


def test_get_db_is_async_generator_function():
    """get_db must be an async generator function (declared with 'async def' + 'yield')."""
    assert inspect.isasyncgenfunction(get_db)


def test_get_db_call_returns_async_gen_object():
    """Calling get_db() returns an async generator object without touching the DB."""
    gen = get_db()
    assert inspect.isasyncgen(gen)
    # We deliberately do NOT advance the generator — advancing it would trigger
    # 'async with AsyncSessionLocal() as session' which requires a live DB.


# ---------------------------------------------------------------------------
# Integration tests — require a live PostgreSQL (auto-skipped otherwise)
# ---------------------------------------------------------------------------

@pytest.mark.integration
@db_available
async def test_get_db_lifecycle_with_live_db():
    """get_db yields an active AsyncSession and can execute a real query."""
    from sqlalchemy import text

    gen = get_db()
    session = await gen.__anext__()
    try:
        assert isinstance(session, AsyncSession)
        assert session.is_active is True
        result = await session.execute(text("SELECT 1"))
        assert result.scalar() == 1
    finally:
        await gen.aclose()


@pytest.mark.integration
@db_available
async def test_select_1_via_engine():
    """The async engine can open a connection and execute SELECT 1."""
    from sqlalchemy import text

    async with engine.connect() as conn:
        result = await conn.execute(text("SELECT 1"))
        assert result.scalar() == 1
