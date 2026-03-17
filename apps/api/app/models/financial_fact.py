"""
FinancialFact model.

Schema source: docs/02-database-schema.md §11 financial_facts.

A financial fact is one extracted value for one canonical field within one
financial period. Facts are immutable: re-parsing creates new facts rather
than overwriting existing ones (the unique constraint on
(financial_period_id, fact_name) enforces this at the database level; a
future supersession mechanism will handle replacing stale facts while
preserving history).

Canonical fact names (fact_name column values) are defined in:
  docs/decisions/001-canonical-fact-names.md

IMPORTANT: fact_value is nullable. A missing value must remain NULL —
never default to 0.0 (per CLAUDE.md: "Never silently convert missing values
to zero"). Downstream metrics and signals must handle NULL explicitly.

See also: docs/05-parser-design.md §Canonical fact schema
"""

import uuid
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.filing import Filing, FilingDocument
    from app.models.financial_period import FinancialPeriod


class FinancialFact(Base, TimestampMixin):
    """
    A single extracted financial fact linked to a period.

    fact_name must be one of the canonical names from:
      docs/decisions/001-canonical-fact-names.md

    fact_value is stored as Decimal(20,2) to preserve monetary precision.
    NULL is the correct representation for a missing value — it is never
    substituted with zero.

    raw_label and canonical_label preserve the provenance of the extraction:
    - raw_label: the string as it appeared in the source document
    - canonical_label: the human-readable canonical name (e.g. "Net assets / liabilities")
    These are display/audit fields; fact_name is the machine key.

    extraction_confidence is per-fact (0.0–1.0). It may differ from the
    parent financial_period.extraction_confidence, which is an aggregate.

    is_derived flags values calculated from other facts rather than directly
    extracted from a document (e.g. gross_profit derived as revenue - cost_of_sales).
    """

    __tablename__ = "financial_facts"

    __table_args__ = (
        UniqueConstraint(
            "financial_period_id",
            "fact_name",
            name="uq_financial_facts",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    financial_period_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("financial_periods.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    fact_name: Mapped[str] = mapped_column(String(128), nullable=False)
    # NULL means the value was not extractable — never default to 0
    fact_value: Mapped[Optional[Decimal]] = mapped_column(Numeric(20, 2))
    unit: Mapped[Optional[str]] = mapped_column(String(32), default="GBP")
    # Provenance — raw label from source document
    raw_label: Mapped[Optional[str]] = mapped_column(Text)
    # Human-readable canonical display label (not the machine key)
    canonical_label: Mapped[Optional[str]] = mapped_column(String(128))
    source_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filing_documents.id", ondelete="SET NULL"),
    )
    source_filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="SET NULL"),
    )
    extraction_method: Mapped[Optional[str]] = mapped_column(String(64))
    # Per-fact confidence; NULL means not yet scored (not 0.0)
    extraction_confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    is_derived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    financial_period: Mapped["FinancialPeriod"] = relationship(
        back_populates="facts"
    )
    company: Mapped["Company"] = relationship(back_populates="financial_facts")
    source_document: Mapped[Optional["FilingDocument"]] = relationship(
        foreign_keys=[source_document_id],
    )
    source_filing: Mapped[Optional["Filing"]] = relationship(
        foreign_keys=[source_filing_id],
    )
