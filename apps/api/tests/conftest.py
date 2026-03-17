"""
Pytest fixtures for the CompanyScope API test suite.

A live PostgreSQL database is required for migration and model tests.
Set TEST_DATABASE_URL to an asyncpg connection string, e.g.:

    export TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/companyscope_test

Tests that need a database are decorated with @pytest.mark.requires_db and are
skipped automatically when TEST_DATABASE_URL is not set.
"""

import os

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

# ---------------------------------------------------------------------------
# Skip marker — apply to any test that requires a live database
# ---------------------------------------------------------------------------

requires_db = pytest.mark.skipif(
    not os.getenv("TEST_DATABASE_URL"),
    reason="TEST_DATABASE_URL not set — skipping database test",
)


# ---------------------------------------------------------------------------
# Database engine / session fixtures
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def test_database_url() -> str:
    """Return TEST_DATABASE_URL or skip the session."""
    url = os.getenv("TEST_DATABASE_URL")
    if not url:
        pytest.skip("TEST_DATABASE_URL not set")
    return url


@pytest_asyncio.fixture(scope="session")
async def db_engine(test_database_url: str):
    """Session-scoped async engine pointing at the test database."""
    engine = create_async_engine(test_database_url, echo=False)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def db_session(db_engine) -> AsyncSession:
    """
    Function-scoped async session.

    Each test runs inside a transaction that is rolled back on completion,
    leaving the database clean for the next test.
    """
    async with db_engine.connect() as conn:
        await conn.begin()
        session_factory = async_sessionmaker(
            bind=conn, class_=AsyncSession, expire_on_commit=False
        )
        async with session_factory() as session:
            yield session
        await conn.rollback()
