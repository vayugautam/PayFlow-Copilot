"""Asynchronous database engine and session management.

Configured with SQLAlchemy 2.0 async engine and psycopg 3 driver, providing
connection pooling and safe FastAPI session dependency lifecycles.
"""

from collections.abc import AsyncGenerator
import asyncio
import sys
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.core.config import get_settings

settings = get_settings()

# Psycopg's Windows async implementation requires the selector event loop.
# Apply this before creating the engine so the application and CLI workers
# use the same policy as the test suite.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

# Create singleton async engine
# - pool_size: baseline persistent connection count
# - max_overflow: transient connections allowed during peak bursts
# - pool_pre_ping: tests liveness before checkout to prevent stale connections
# - pool_recycle: recycles connections after 1 hour to prevent DB timeout drops
engine: AsyncEngine = create_async_engine(
    settings.DATABASE_URL,
    echo=settings.DEBUG,
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,
    pool_recycle=3600,
)

# Async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency yielding an async database session per request.

    Guarantees session cleanup upon request completion.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()
