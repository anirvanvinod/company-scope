"""
PscRecord model — Persons with Significant Control.

Schema source: docs/02-database-schema.md §7 psc_records.

PSC records include both individual persons and corporate/legal entities
(indicated by the kind field). ceased_on being NULL indicates a current PSC.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, SmallInteger, String, Text
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class PscRecord(Base, TimestampMixin):
    """
    A person with significant control record for a company.

    natures_of_control is stored as a text array matching the Companies
    House API response (e.g. ["ownership-of-shares-25-to-50-percent"]).
    """

    __tablename__ = "psc_records"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    psc_external_id: Mapped[Optional[str]] = mapped_column(Text)
    kind: Mapped[Optional[str]] = mapped_column(String(64))
    name: Mapped[Optional[str]] = mapped_column(Text)
    notified_on: Mapped[Optional[date]] = mapped_column(Date)
    ceased_on: Mapped[Optional[date]] = mapped_column(Date)
    nationality: Mapped[Optional[str]] = mapped_column(Text)
    country_of_residence: Mapped[Optional[str]] = mapped_column(Text)
    # Month and year only (privacy — same reasoning as officers)
    date_of_birth_month: Mapped[Optional[int]] = mapped_column(SmallInteger)
    date_of_birth_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    natures_of_control: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    address: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="psc_records")
