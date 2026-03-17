"""
Alembic environment configuration.

Uses an async engine (asyncpg) via connection.run_sync() so no separate
sync driver (psycopg2) is required. The database URL is loaded from
app.config.settings to keep credentials out of alembic.ini.

URL resolution order:
  1. TEST_DATABASE_URL env var — used when running migration tests so that
     test infrastructure does not require DATABASE_URL to be set separately.
  2. settings.database_url — used in all other contexts (production, local dev).

To run migrations:
    cd apps/api
    uv run alembic upgrade head

To generate a new migration after model changes:
    uv run alembic revision --autogenerate -m "description"
"""

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy.ext.asyncio import create_async_engine

# Import Base and all models so metadata is fully populated.
# This is required for autogenerate to detect schema changes.
from app.db.base import Base
import app.models  # noqa: F401 — registers all models with Base.metadata
from app.config import settings

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def _effective_database_url() -> str:
    """
    Return the database URL to use for migrations.

    Prefers TEST_DATABASE_URL when set so that migration tests target the
    test database rather than the application database configured in settings.
    Falls back to settings.database_url for all other contexts.
    """
    return os.getenv("TEST_DATABASE_URL") or settings.database_url


def run_migrations_offline() -> None:
    """
    Run migrations without a live DB connection (generates SQL to stdout).
    Uses a synchronous-compatible URL (strips the +asyncpg driver prefix).
    """
    url = _effective_database_url().replace("+asyncpg", "")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:  # type: ignore[no-untyped-def]
    """Called synchronously inside an async connection via run_sync()."""
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Create an async engine and run migrations via run_sync()."""
    engine = create_async_engine(_effective_database_url(), echo=False)
    async with engine.connect() as conn:
        await conn.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
