"""
Async database engine and session factory.

Usage in FastAPI route dependencies:

    from app.db.session import get_session
    from sqlalchemy.ext.asyncio import AsyncSession

    @router.get("/example")
    async def example(session: AsyncSession = Depends(get_session)):
        ...

Session lifecycle: each request gets one session that is rolled back on
error and closed on completion. Transactions are managed by the caller.
"""

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
    pool_size=10,
    max_overflow=20,
    pool_pre_ping=True,  # detect stale connections before use
)

async_session_factory = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency: yields a scoped async database session."""
    async with async_session_factory() as session:
        try:
            yield session
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
