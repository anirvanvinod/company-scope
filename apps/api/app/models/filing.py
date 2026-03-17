"""
Filing and FilingDocument models.

Schema source: docs/02-database-schema.md §3 filings, §4 filing_documents.

Filings are the Companies House filing history items. FilingDocuments are
the individual document artefacts associated with a filing, including their
fetch and parse status for the document pipeline.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import BigInteger, Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company
    from app.models.financial_period import FinancialPeriod
    from app.models.ops import ExtractionRun


class Filing(Base, TimestampMixin):
    """
    A filing history item from Companies House.

    transaction_id is the Companies House identifier for the filing.
    source_links preserves the original links payload from the API.
    """

    __tablename__ = "filings"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    transaction_id: Mapped[str] = mapped_column(String(64), nullable=False)
    category: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    type: Mapped[Optional[str]] = mapped_column(String(32), index=True)
    description: Mapped[Optional[str]] = mapped_column(Text)
    description_values: Mapped[Optional[dict]] = mapped_column(JSONB)
    action_date: Mapped[Optional[date]] = mapped_column(Date)
    date_filed: Mapped[Optional[date]] = mapped_column(Date)
    pages: Mapped[Optional[int]] = mapped_column(Integer)
    barcode: Mapped[Optional[str]] = mapped_column(Text)
    paper_filed: Mapped[Optional[bool]] = mapped_column(Boolean)
    source_links: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="filings")
    documents: Mapped[list["FilingDocument"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        back_populates="filing"
    )
    financial_periods: Mapped[list["FinancialPeriod"]] = relationship(
        back_populates="filing"
    )

    # Unique constraint defined in migration: UNIQUE(company_id, transaction_id)


class FilingDocument(Base, TimestampMixin):
    """
    Document metadata and local caching status for a filing's associated document.

    fetch_status tracks whether the document has been downloaded to MinIO.
    parse_status tracks whether the financial parser has processed it.

    Controlled vocabularies (per docs/02 §Suggested enums):
      fetch_status: pending | fetched | unavailable | failed
      parse_status: pending | parsed | unsupported | failed
    """

    __tablename__ = "filing_documents"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    filing_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("filings.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    document_id: Mapped[str] = mapped_column(String(128), unique=True, nullable=False)
    original_filename: Mapped[Optional[str]] = mapped_column(Text)
    content_length: Mapped[Optional[int]] = mapped_column(BigInteger)
    content_type: Mapped[Optional[str]] = mapped_column(Text)
    available_content_types: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    storage_key: Mapped[Optional[str]] = mapped_column(Text)
    storage_etag: Mapped[Optional[str]] = mapped_column(Text)
    fetch_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    parse_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="pending", index=True
    )
    downloaded_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    metadata_payload: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    filing: Mapped["Filing"] = relationship(back_populates="documents")
    extraction_runs: Mapped[list["ExtractionRun"]] = relationship(
        back_populates="filing_document"
    )
