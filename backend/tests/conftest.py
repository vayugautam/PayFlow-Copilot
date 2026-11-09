"""Pytest configuration and shared test fixtures."""

import asyncio
import os
import sys
from pathlib import Path

import pytest

# Ensure 'backend/' is on sys.path so that `from app.xxx import yyy` resolves
# regardless of the directory from which pytest is invoked.
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

# Establish a safe, isolated test environment before any application imports.
os.environ.setdefault("APP_ENV", "testing")
# Keep externally supplied valid boolean values, but prevent unrelated shell
# variables such as DEBUG=release from breaking settings construction.
if os.environ.get("DEBUG", "").lower() not in {
    "true",
    "false",
    "1",
    "0",
    "yes",
    "no",
    "on",
    "off",
}:
    os.environ["DEBUG"] = "true"
os.environ.setdefault(
    "SECRET_KEY",
    "testing-secret-key-at-least-32-chars-long-2026",
)

# Use the explicitly configured test database for imported application settings.
# Never derive it from DATABASE_URL, which may point at the application database.
if os.environ.get("TEST_DATABASE_URL"):
    os.environ["DATABASE_URL"] = os.environ["TEST_DATABASE_URL"]


def _configure_windows_event_loop_policy() -> None:
    """Configure the loop policy before pytest creates async test loops."""
    if sys.platform == "win32":
        # Psycopg async operations require SelectorEventLoop on Windows;
        # ProactorEventLoop is not supported by the async driver.
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


_configure_windows_event_loop_policy()


@pytest.fixture(autouse=True)
def reset_process_rate_limits():
    from app.core.observability import rate_limiter

    rate_limiter.reset()
    yield
    rate_limiter.reset()


def pytest_configure(config) -> None:
    """Reassert the Windows policy during pytest's early configuration."""
    _configure_windows_event_loop_policy()
