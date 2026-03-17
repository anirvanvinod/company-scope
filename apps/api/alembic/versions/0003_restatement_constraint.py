"""Update financial_periods unique constraint to include is_restated.

Revision ID: 0003
Revises: 0002
Create Date: 2026-03-17

Replaces the unique constraint on financial_periods from:
  UNIQUE (company_id, period_end, accounts_type)
with:
  UNIQUE (company_id, period_end, accounts_type, is_restated)

This allows one original row (is_restated=False) and one restated row
(is_restated=True) to coexist for the same period, satisfying the
non-overwrite requirement from docs/05-parser-design.md.

See: docs/decisions/003-restatement-strategy.md
"""

from typing import Sequence, Union

from alembic import op

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_constraint("uq_financial_periods", "financial_periods", type_="unique")
    op.create_unique_constraint(
        "uq_financial_periods",
        "financial_periods",
        ["company_id", "period_end", "accounts_type", "is_restated"],
    )


def downgrade() -> None:
    op.drop_constraint("uq_financial_periods", "financial_periods", type_="unique")
    op.create_unique_constraint(
        "uq_financial_periods",
        "financial_periods",
        ["company_id", "period_end", "accounts_type"],
    )
