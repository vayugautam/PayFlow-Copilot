"""Real PostgreSQL integration fixtures with migration and isolation guards."""

import os
import socket
import subprocess
import sys
from pathlib import Path
from urllib.parse import urlparse

import pytest
import pytest_asyncio
from sqlalchemy import text

BACKEND_DIR = Path(__file__).resolve().parents[2]


def _database_url() -> str | None:
    return os.environ.get("TEST_DATABASE_URL")


def _skip_reason() -> str | None:
    value = _database_url()
    if not value:
        return "TEST_DATABASE_URL is not configured; PostgreSQL integration tests skipped"
    parsed = urlparse(value)
    database_name = parsed.path.lstrip("/")
    if not database_name:
        return "TEST_DATABASE_URL has no database name; integration tests skipped"
    if database_name == "payflow_copilot":
        return "TEST_DATABASE_URL points at the development database; integration tests skipped"
    host = parsed.hostname or "localhost"
    try:
        with socket.create_connection((host, parsed.port or 5432), timeout=1):
            return None
    except OSError as exc:
        return f"TEST_DATABASE_URL PostgreSQL is unreachable ({exc}); integration tests skipped"


@pytest.fixture(scope="session")
def migrated_postgres():
    reason = _skip_reason()
    if reason:
        pytest.skip(reason)
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        cwd=BACKEND_DIR,
        env=os.environ.copy(),
        capture_output=True,
        text=True,
    )
    if result.returncode:
        pytest.fail(f"Alembic migration failed:\n{result.stdout}\n{result.stderr}")
    yield


@pytest_asyncio.fixture
async def integration_db(migrated_postgres):
    from app.db.session import AsyncSessionLocal

    async with AsyncSessionLocal() as session:
        yield session
        await session.rollback()


@pytest_asyncio.fixture(autouse=True)
async def clean_integration_data(migrated_postgres):
    yield
    from app.db.session import engine

    async with engine.begin() as connection:
        await connection.execute(
            text(
                "TRUNCATE TABLE audit_logs, disputes, messages, conversations, "
                "knowledge_documents, payment_webhook_events, payment_orders, "
                "transactions, users RESTART IDENTITY CASCADE"
            )
        )
