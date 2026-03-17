"""
Charge model — registered charges against a company.

Schema source: docs/02-database-schema.md §8 charges.

Charges indicate secured financing arrangements. Their presence is
context, not automatically a risk signal (per docs/06-methodology.md
§Charges — financing context, not automatically negative evidence).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Date, DateTime, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class Charge(Base, TimestampMixin):
    """
    A registered charge against a company.

    charge_id is the Companies House charge identifier.
    persons_entitled and particulars are stored as JSONB to preserve the
    original structured data from Companies House.

    Controlled vocabulary for status: outstanding | satisfied | part-satisfied | none.
    """

    __tablename__ = "charges"

    __table_args__ = (
        UniqueConstraint("company_id", "charge_id", name="uq_charges"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    charge_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    delivered_on: Mapped[Optional[date]] = mapped_column(Date)
    created_on: Mapped[Optional[date]] = mapped_column(Date)
    resolved_on: Mapped[Optional[date]] = mapped_column(Date)
    persons_entitled: Mapped[Optional[dict]] = mapped_column(JSONB)
    particulars: Mapped[Optional[dict]] = mapped_column(JSONB)
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="charges")
