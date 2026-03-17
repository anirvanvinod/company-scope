"""
InsolvencyCase model.

Schema source: docs/02-database-schema.md §9 insolvency_cases.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class InsolvencyCase(Base, TimestampMixin):
    """
    Public insolvency case record.

    Data availability varies by case type and practitioner disclosure.
    practitioner and notes are stored as JSONB to accommodate variable
    structure from Companies House.
    """

    __tablename__ = "insolvency_cases"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    case_number: Mapped[Optional[str]] = mapped_column(Text)
    case_type: Mapped[Optional[str]] = mapped_column(String(64))
    petition_date: Mapped[Optional[date]] = mapped_column(Date)
    order_date: Mapped[Optional[date]] = mapped_column(Date)
    notes: Mapped[Optional[dict]] = mapped_column(JSONB)
    practitioner: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="insolvency_cases")
