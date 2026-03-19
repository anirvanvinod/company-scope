"""
Pytest fixtures for the CompanyScope API test suite.

A live PostgreSQL database is required for migration and model tests.
Set TEST_DATABASE_URL to an asyncpg connection string, e.g.:

    export TEST_DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/companyscope_test

Tests that need a database are decorated with @pytest.mark.requires_db and are
skipped automatically when TEST_DATABASE_URL is not set.

Route tests use async_client + mock_session (no live DB required).
"""

import os
import uuid as _uuid
from unittest.mock import AsyncMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
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


# ---------------------------------------------------------------------------
# Route-level fixtures (no live DB — mock session injected via DI override)
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_session() -> AsyncMock:
    """
    An AsyncMock that stands in for an AsyncSession.

    Route tests set return values on specific query functions; the mock session
    is injected via FastAPI's dependency_overrides mechanism in async_client.
    """
    return AsyncMock(spec=AsyncSession)


@pytest_asyncio.fixture
async def async_client(mock_session: AsyncMock) -> AsyncClient:
    """
    An httpx AsyncClient wired to the FastAPI app with the DB session mocked.

    Imports are deferred so that importing this fixture does not attempt a
    real DB connection (the engine is initialised at module import time).
    """
    from app.db.session import get_session
    from app.main import app

    async def override_get_session():
        yield mock_session

    app.dependency_overrides[get_session] = override_get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_session, None)


# ---------------------------------------------------------------------------
# Authenticated client — mocks both session and get_current_user
# ---------------------------------------------------------------------------

_MOCK_USER_ID = _uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
_MOCK_USER = {
    "id": _MOCK_USER_ID,
    "email": "test@example.com",
    "display_name": "Test User",
    "auth_provider": "password",
}


@pytest.fixture
def mock_user() -> dict:
    """Return the canonical mock user dict used in auth / watchlist tests."""
    return _MOCK_USER


@pytest_asyncio.fixture
async def auth_client(mock_session: AsyncMock) -> AsyncClient:
    """
    An httpx AsyncClient that bypasses JWT verification by overriding
    get_current_user to return the mock user directly.

    Use this fixture for tests of endpoints that require authentication
    (watchlists, /me).  For endpoints under /auth/* use async_client.
    """
    from app.auth import get_current_user
    from app.db.session import get_session
    from app.main import app

    async def override_get_session():
        yield mock_session

    async def override_get_current_user():
        return _MOCK_USER

    app.dependency_overrides[get_session] = override_get_session
    app.dependency_overrides[get_current_user] = override_get_current_user
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.pop(get_session, None)
    app.dependency_overrides.pop(get_current_user, None)
