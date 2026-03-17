"""
Async database engine and session factory for the worker service.

Usage inside async functions:

    from app.db import get_session

    async with get_session() as session:
        await session.execute(...)
        await session.commit()

Unlike the API's FastAPI dependency, this is a plain async context manager
because Celery tasks drive the lifecycle (not the request/response cycle).
"""

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=False,
    pool_size=5,
    max_overflow=10,
    pool_pre_ping=True,
)

_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """Yield a scoped async DB session; rolls back on error, always closes."""
    async with _session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
