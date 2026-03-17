"""Financial domain — financial_periods and financial_facts tables.

Revision ID: 0002
Revises: 0001
Create Date: 2026-03-17

Implements Phase 1B financial domain schema.

Tables added:
  + financial_periods   (docs/02-database-schema.md §10)
  + financial_facts     (docs/02-database-schema.md §11)

Canonical fact_name values follow docs/decisions/001-canonical-fact-names.md
(resolved Phase 1B — Option B, docs/05 names adopted):
  revenue, gross_profit, operating_profit_loss, profit_loss_after_tax,
  current_assets, fixed_assets, total_assets_less_current_liabilities,
  creditors_due_within_one_year, creditors_due_after_one_year,
  net_assets_liabilities, cash_bank_on_hand, average_number_of_employees

Important: fact_value is nullable. NULL represents a missing value and must
never be defaulted to 0 (per CLAUDE.md data discipline rules).
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # financial_periods
    # Represents one reporting period extracted from an accounts filing.
    # Unique on (company_id, period_end, accounts_type) so there is one
    # canonical period record per company per period end per accounts type.
    # ------------------------------------------------------------------
    op.create_table(
        "financial_periods",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("period_start", sa.Date, nullable=True),
        sa.Column("period_end", sa.Date, nullable=False),
        sa.Column("period_length_days", sa.Integer, nullable=True),
        sa.Column("accounts_type", sa.String(64), nullable=True),
        sa.Column("accounting_standard", sa.String(64), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=True, server_default="GBP"),
        sa.Column(
            "is_restated", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column("comparison_period_end", sa.Date, nullable=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filing_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "company_id",
            "period_end",
            "accounts_type",
            name="uq_financial_periods",
        ),
    )

    op.create_index(
        "idx_financial_periods_company",
        "financial_periods",
        ["company_id", sa.text("period_end DESC")],
    )
    op.create_index(
        "idx_financial_periods_filing",
        "financial_periods",
        ["filing_id"],
    )

    # ------------------------------------------------------------------
    # financial_facts
    # One extracted value per canonical fact name per financial period.
    # fact_value is nullable — NULL means the value was not extractable.
    # Unique on (financial_period_id, fact_name).
    # ------------------------------------------------------------------
    op.create_table(
        "financial_facts",
        sa.Column(
            "id",
            postgresql.UUID(as_uuid=True),
            primary_key=True,
        ),
        sa.Column(
            "financial_period_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("financial_periods.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "company_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("companies.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("fact_name", sa.String(128), nullable=False),
        # NULL = value not extractable. Never default to 0.
        sa.Column("fact_value", sa.Numeric(20, 2), nullable=True),
        sa.Column("unit", sa.String(32), nullable=True, server_default="GBP"),
        sa.Column("raw_label", sa.Text, nullable=True),
        sa.Column("canonical_label", sa.String(128), nullable=True),
        sa.Column(
            "source_document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filing_documents.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_filing_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("filings.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("extraction_method", sa.String(64), nullable=True),
        # NULL = confidence not yet scored. Never default to 0.
        sa.Column("extraction_confidence", sa.Numeric(5, 4), nullable=True),
        sa.Column(
            "is_derived", sa.Boolean, nullable=False, server_default=sa.false()
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.UniqueConstraint(
            "financial_period_id",
            "fact_name",
            name="uq_financial_facts",
        ),
    )

    op.create_index(
        "idx_financial_facts_company_fact",
        "financial_facts",
        ["company_id", "fact_name"],
    )
    op.create_index(
        "idx_financial_facts_period",
        "financial_facts",
        ["financial_period_id"],
    )


def downgrade() -> None:
    op.drop_index("idx_financial_facts_period", table_name="financial_facts")
    op.drop_index("idx_financial_facts_company_fact", table_name="financial_facts")
    op.drop_table("financial_facts")

    op.drop_index("idx_financial_periods_filing", table_name="financial_periods")
    op.drop_index("idx_financial_periods_company", table_name="financial_periods")
    op.drop_table("financial_periods")
