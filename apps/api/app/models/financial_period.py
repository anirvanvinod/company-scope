"""
FinancialPeriod model.

Schema source: docs/02-database-schema.md §10 financial_periods.

A financial period represents one reporting period extracted from an accounts
filing for a company. It is the parent record for all financial_facts for that
period. Facts are immutable per period; re-parsing creates a new period record
(or updates extraction_confidence on the existing one if the period_end and
accounts_type match and the new run supersedes).

The unique constraint on (company_id, period_end, accounts_type) enforces
one canonical period per company per period-end per accounts type. If a
filing is restated, is_restated=True distinguishes the restated version and
comparison_period_end points to the prior comparative period.

Canonical fact names used in related financial_facts follow:
  docs/decisions/001-canonical-fact-names.md (resolved Phase 1B)

See also: docs/05-parser-design.md §Period handling
"""

import uuid
from datetime import date
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    Date,
    ForeignKey,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.filing import Filing, FilingDocument
    from app.models.financial_fact import FinancialFact


class FinancialPeriod(Base, TimestampMixin):
    """
    One reporting period for a company, sourced from an accounts filing.

    period_end is required — it is the anchor for period-based comparisons.
    period_start is preferred but may be null if not extractable from the
    document (per docs/05 §Period handling — confidence is reduced in that case).

    currency_code defaults to GBP; always preserve the source currency
    when available (docs/05 §Numeric normalisation).

    extraction_confidence is the overall confidence for this period, derived
    from the extraction run. Individual facts carry their own confidence score.
    """

    __tablename__ = "financial_periods"

    __table_args__ = (
        # is_restated is included in the key so that one original (False) and
        # one restated (True) period can coexist for the same company/period-end/
        # accounts_type triple — see docs/decisions/003-restatement-strategy.md.
        UniqueConstraint(
            "company_id",
            "period_end",
            "accounts_type",
            "is_restated",
            name="uq_financial_periods",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="SET NULL"),
    )
    period_start: Mapped[Optional[date]] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    period_length_days: Mapped[Optional[int]] = mapped_column(Integer)
    accounts_type: Mapped[Optional[str]] = mapped_column(String(64))
    accounting_standard: Mapped[Optional[str]] = mapped_column(String(64))
    # Default GBP — must be set from source when available; never silently assumed
    currency_code: Mapped[Optional[str]] = mapped_column(String(3), default="GBP")
    is_restated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    comparison_period_end: Mapped[Optional[date]] = mapped_column(Date)
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filing_documents.id", ondelete="SET NULL"),
    )
    # Overall extraction confidence for this period (0.0–1.0).
    # NULL means confidence has not been scored yet (not 0.0).
    extraction_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="financial_periods")
    filing: Mapped[Optional["Filing"]] = relationship(
        back_populates="financial_periods"
    )
    source_document: Mapped[Optional["FilingDocument"]] = relationship(
        foreign_keys=[source_document_id],
    )
    facts: Mapped[list["FinancialFact"]] = relationship(
        back_populates="financial_period", cascade="all, delete-orphan"
    )
