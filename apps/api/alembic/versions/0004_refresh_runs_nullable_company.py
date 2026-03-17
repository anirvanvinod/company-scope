"""Make refresh_runs.company_id nullable.

Revision ID: 0004
Revises: 0003
Create Date: 2026-03-17

Problem:
    refresh_runs.company_id was created NOT NULL in 0001.
    The worker's create_refresh_run() passes company_id=None for full
    refreshes (trigger_type='full') because the DB UUID is not known
    until after the upstream CH API call and upsert_company() completes.
    This caused a PostgreSQL NOT NULL constraint violation on every full
    refresh.

Fix:
    Drop the NOT NULL constraint so company_id can be NULL.
    The FK and ON DELETE CASCADE are preserved — they only fire when
    company_id IS NOT NULL, so NULL-company audit rows are unaffected
    by company deletion.

Downstream effects:
    - Partial refreshes (filings, officers, pscs, charges) already pass
      a resolved company_id and are unaffected.
    - Full refresh runs now have company_id=NULL in the DB until the
      company is upserted.  This is acceptable for an audit log.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "0004"
down_revision: Union[str, None] = "0003"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "refresh_runs",
        "company_id",
        nullable=True,
        existing_type=None,  # type already in DB; not changing type, only nullability
    )


def downgrade() -> None:
    # NOTE: this will fail if any rows have company_id=NULL.
    # Clear them or back-fill a sentinel value first.
    op.alter_column(
        "refresh_runs",
        "company_id",
        nullable=False,
        existing_type=None,
    )
