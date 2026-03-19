"""
Async database session factory for the worker service.

Usage inside async functions:

    from app.db import get_session

    async with get_session() as session:
        await session.execute(...)
        await session.commit()

Unlike the API's FastAPI dependency, this is a plain async context manager
because Celery tasks drive the lifecycle (not the request/response cycle).

Design note — engine-per-session:
    Celery uses asyncio.run() which creates a new event loop per task.
    asyncpg connections bind to the event loop they are created on.
    Creating the engine inside get_session() ensures the connection is always
    on the current loop, avoiding "Future attached to a different loop" errors.
    NullPool is used so SQLAlchemy never reuses connections across calls.
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.pool import NullPool

from app.config import settings


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped async DB session; rolls back on error, always closes."""
    engine = create_async_engine(
        settings.database_url,
        echo=False,
        poolclass=NullPool,
    )
    session_factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    async with session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    await engine.dispose()
