"""Phase 6A analysis schema — derived_metrics table and risk_signals unique constraint.

Revision ID: 0006
Revises: 0005
Create Date: 2026-03-18

Changes:

  + derived_metrics table
      Stores the deterministic derived metrics computed from financial_facts
      (M1–M9 per docs/09-financial-analysis-spec.md).  One row per
      (company_id, financial_period_id, metric_key).

      metric_value is nullable — NULL means the metric could not be computed
      (missing inputs, zero denominator, period gap, low confidence).

  + uq_risk_signals unique constraint on risk_signals(company_id, signal_code)
      The risk_signals table was created in 0001 but without a unique
      constraint.  Phase 6A adds it so the analysis task can upsert the
      current signal state via ON CONFLICT DO UPDATE.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0006"
down_revision: Union[str, None] = "0005"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # derived_metrics
    # Computed from financial_facts by the analysis worker task.
    # Rebuilt on every metric recompute run.
    # ------------------------------------------------------------------
    op.create_table(
        "derived_metrics",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "financial_period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "prior_period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("metric_key", sa.String(64), nullable=False),
        # NULL = metric not computable (missing inputs, zero denominator,
        # period gap, or insufficient confidence).  Never default to 0.
        sa.Column("metric_value", sa.Numeric(20, 6), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True),
        sa.Column("confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column("confidence_band", sa.String(16), nullable=True),
        sa.Column("warnings", postgresql.JSONB(), nullable=True),
        sa.Column("methodology_version", sa.String(16), nullable=False),
        sa.Column(
            "generated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "company_id",
            "financial_period_id",
            "metric_key",
            name="uq_derived_metrics",
        ),
    )
    op.create_index(
        "idx_derived_metrics_company_period",
        "derived_metrics",
        ["company_id", "financial_period_id"],
    )
    op.create_index(
        "idx_derived_metrics_key",
        "derived_metrics",
        ["company_id", "metric_key"],
    )

    # ------------------------------------------------------------------
    # risk_signals unique constraint
    # Allows ON CONFLICT DO UPDATE upsert by (company_id, signal_code).
    # ------------------------------------------------------------------
    op.create_unique_constraint(
        "uq_risk_signals",
        "risk_signals",
        ["company_id", "signal_code"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_risk_signals", "risk_signals", type_="unique")
    op.drop_index("idx_derived_metrics_key", table_name="derived_metrics")
    op.drop_index("idx_derived_metrics_company_period", table_name="derived_metrics")
    op.drop_table("derived_metrics")
