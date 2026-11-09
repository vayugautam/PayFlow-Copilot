"""Database connectivity verification script for PayFlow Copilot.

Tests asynchronous database connectivity using SQLAlchemy 2.0 and psycopg 3,
executes a ping query (`SELECT 1`), and cleanly releases connections.
Credentials are never displayed in logs.
"""

import asyncio
import sys
import time
from pathlib import Path

# Add backend directory to sys.path so script can be run from any working directory
BACKEND_DIR = Path(__file__).resolve().parent.parent
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))

from sqlalchemy import text
from app.core.config import get_settings
from app.db.session import engine


async def verify_database_connection() -> bool:
    """Verify async PostgreSQL connectivity and execute SELECT 1."""
    settings = get_settings()

    print("=" * 60)
    print(f"PayFlow Copilot — Database Connectivity Verification")
    print(f"Environment : {settings.APP_ENV}")
    print(f"Target URL  : {settings.masked_database_url}")
    print("=" * 60)

    start_time = time.perf_counter()

    try:
        print("[1/3] Initiating async connection pool checkout...")
        async with engine.connect() as conn:
            elapsed_connect = (time.perf_counter() - start_time) * 1000
            print(f"[2/3] Connection established in {elapsed_connect:.2f}ms.")
            print("[2/3] Executing ping query ('SELECT 1')...")

            result = await conn.execute(text("SELECT 1"))
            scalar_value = result.scalar()

            if scalar_value != 1:
                print(f"[ERROR] Expected query result '1', got: {scalar_value}")
                return False

            total_elapsed = (time.perf_counter() - start_time) * 1000
            print(f"[3/3] Query succeeded! Response: {scalar_value} ({total_elapsed:.2f}ms total)")

        print("=" * 60)
        print(" SUCCESS: Database is reachable and responding correctly.")
        print("=" * 60)
        return True

    except Exception as exc:
        print("=" * 60)
        print(" FAILED: Database connection error occurred.")
        print("=" * 60)
        print(f"Error Type: {type(exc).__name__}")
        print(f"Details   : {exc}")
        print("\nTroubleshooting recommendations:")
        print("1. Verify that PostgreSQL is running on the target host/port.")
        print("2. Ensure the database specified in DATABASE_URL exists.")
        print("3. Check credentials in backend/.env (user, password, host, port).")
        print("4. If running locally with Docker, verify container status:")
        print("   docker ps")
        print("=" * 60)
        return False

    finally:
        # Guarantee all pooled connections are released
        await engine.dispose()


def _run_verification() -> bool:
    """Run the verification coroutine with a psycopg-compatible event loop."""
    if sys.platform == "win32":
        # Psycopg async operations require SelectorEventLoop on Windows;
        # ProactorEventLoop is not supported by the async driver.
        return asyncio.run(
            verify_database_connection(),
            loop_factory=asyncio.SelectorEventLoop,
        )
    return asyncio.run(verify_database_connection())


def main() -> None:
    """Entry point for CLI execution."""
    success = _run_verification()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
