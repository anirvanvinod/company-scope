"""Phase 6B analysis layer — snapshot_build_runs table.

Revision ID: 0007
Revises: 0006
Create Date: 2026-03-18

Changes:

  + snapshot_build_runs table
      Audit log of snapshot build attempts.  One row per invocation of the
      build_snapshot Celery task.  Used for observability, debugging, and
      freshness tracking.

      Columns:
        id               UUID primary key
        company_id       FK → companies (nullable for manual/admin builds)
        status           pending | running | completed | failed
        summary_source   ai | template | null (populated on completion)
        methodology_version  string (populated on completion)
        started_at       timestamp with timezone
        finished_at      timestamp with timezone (null until complete)
        error_summary    text (null unless status=failed)

  Note: the company_snapshots table already exists from migration 0001.
  This migration only adds the build-run audit table.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0007"
down_revision: Union[str, None] = "0006"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "snapshot_build_runs",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("summary_source", sa.String(16), nullable=True),
        sa.Column("methodology_version", sa.String(32), nullable=True),
        sa.Column(
            "started_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error_summary", sa.Text, nullable=True),
    )

    op.create_index(
        "idx_snapshot_build_runs_company_id",
        "snapshot_build_runs",
        ["company_id"],
    )
    op.create_index(
        "idx_snapshot_build_runs_status",
        "snapshot_build_runs",
        ["status"],
    )


def downgrade() -> None:
    op.drop_index("idx_snapshot_build_runs_status", table_name="snapshot_build_runs")
    op.drop_index("idx_snapshot_build_runs_company_id", table_name="snapshot_build_runs")
    op.drop_table("snapshot_build_runs")
