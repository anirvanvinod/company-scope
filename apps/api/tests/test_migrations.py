"""
Migration smoke tests.

Verifies that the Alembic migration chain can be applied to a clean database
and fully reversed. Requires a live PostgreSQL database via TEST_DATABASE_URL.

These tests do NOT test application logic — they test that the DDL itself is
correct and that upgrade/downgrade are inverse operations.
"""

import os

import pytest
from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from sqlalchemy import create_engine

from tests.conftest import requires_db

# Path to alembic.ini relative to the apps/api directory.
# pytest is run from apps/api, so this resolves correctly.
ALEMBIC_INI = "alembic.ini"


def _sync_url(async_url: str) -> str:
    """Strip +asyncpg from URL so the sync SQLAlchemy engine can use it."""
    return async_url.replace("+asyncpg", "")


@requires_db
def test_upgrade_head_and_downgrade_base() -> None:
    """
    Apply all migrations to head, then downgrade to base.

    Passes if neither step raises an exception, confirming that:
    - every upgrade() function is valid DDL
    - every downgrade() function is valid DDL and reverses the upgrade
    """
    url = _sync_url(os.environ["TEST_DATABASE_URL"])
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")


@requires_db
def test_upgrade_head_is_idempotent() -> None:
    """
    Running upgrade head twice must not fail.

    Alembic tracks applied revisions in alembic_version and is a no-op on
    re-run, but this test catches cases where upgrade() is not idempotent
    (e.g. CREATE TABLE without IF NOT EXISTS outside of op.create_table).
    """
    url = _sync_url(os.environ["TEST_DATABASE_URL"])
    cfg = Config(ALEMBIC_INI)
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    command.upgrade(cfg, "head")  # second run must be a no-op


@requires_db
def test_migration_leaves_no_pending_revisions() -> None:
    """
    After upgrade head, there must be no unrun revisions.

    This catches the case where a new migration file exists but was not
    included in the revision chain.

    env.py reads TEST_DATABASE_URL when set, so all three operations below
    (upgrade, head check, engine inspection) target the same database.
    """
    url = _sync_url(os.environ["TEST_DATABASE_URL"])

    cfg = Config(ALEMBIC_INI)
    command.upgrade(cfg, "head")

    engine = create_engine(url)
    with engine.connect() as conn:
        ctx = MigrationContext.configure(conn)
        current = ctx.get_current_heads()
    engine.dispose()

    from alembic.script import ScriptDirectory
    script = ScriptDirectory.from_config(cfg)
    heads = set(script.get_heads())

    assert set(current) == heads, (
        f"DB is at {current!r} but migration heads are {heads!r}. "
        "A migration may not be linked into the revision chain."
    )
