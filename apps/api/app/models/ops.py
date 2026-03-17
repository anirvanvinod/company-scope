"""
Operational models: RefreshRun and ExtractionRun.

Schema source: docs/02-database-schema.md §18 refresh_runs, §19 extraction_runs.

NOTE on naming: the user requested "parser_runs" and "parser_run_events".
These terms appear in docs/05-parser-design.md but do NOT exist in
docs/02-database-schema.md (the authoritative schema source). docs/02
defines "extraction_runs" for the same concept. See:
  docs/decisions/002-parser-runs-vs-extraction-runs.md

RefreshRun: tracks each attempt to refresh a company's data from Companies House.
ExtractionRun: tracks each attempt to parse a filing document.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.filing import Filing, FilingDocument
    from app.models.user import User


class RefreshRun(Base):
    """
    A single company refresh attempt.

    trigger_type indicates what initiated the refresh:
      on_demand | scheduled | watchlist | manual | streaming_event

    Controlled vocabulary for status: queued | running | completed | failed | partial.

    No updated_at — status transitions are the only mutation; immutability
    is preserved by updating only the status, finished_at, and error_summary.
    """

    __tablename__ = "refresh_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    trigger_type: Mapped[str] = mapped_column(String(32), nullable=False)
    requested_by_user_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
    )
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    error_summary: Mapped[Optional[str]] = mapped_column(Text)
    metadata: Mapped[Optional[dict]] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="refresh_runs")


class ExtractionRun(Base):
    """
    A single document parsing attempt.

    Tracks parser version, outcome, confidence, and any warnings or errors.
    Both filing_id and filing_document_id are nullable (SET NULL on delete)
    so audit history is preserved even if a document or filing is removed.

    Controlled vocabulary for status: pending | running | parsed | unsupported | failed.

    No updated_at — write-once record; status and finished_at are the only
    fields updated after creation.
    """

    __tablename__ = "extraction_runs"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filing_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="SET NULL"),
    )
    filing_document_id: Mapped[Optional[uuid.UUID]] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filing_documents.id", ondelete="SET NULL"),
        index=True,
    )
    parser_version: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[Optional[Decimal]] = mapped_column(Numeric(5, 4))
    warnings: Mapped[Optional[dict]] = mapped_column(JSONB)
    errors: Mapped[Optional[dict]] = mapped_column(JSONB)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    finished_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    filing: Mapped[Optional["Filing"]] = relationship(
        back_populates="extraction_runs"
    )
    filing_document: Mapped[Optional["FilingDocument"]] = relationship(
        back_populates="extraction_runs"
    )
