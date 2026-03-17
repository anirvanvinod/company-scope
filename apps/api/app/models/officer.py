"""
Officer and OfficerAppointment models.

Schema source: docs/02-database-schema.md §5 officers, §6 officer_appointments.

Officers are person or corporate entities. OfficerAppointments link officers
to companies with role and tenure information.

Date of birth is stored only to month/year precision, matching the level of
detail exposed by Companies House (which redacts the day for privacy).
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, SmallInteger, String, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class Officer(Base, TimestampMixin):
    """
    A person or corporate officer entity.

    officer_external_id is the Companies House officer ID where available.
    raw_payload preserves the original API response for auditability.
    """

    __tablename__ = "officers"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    officer_external_id: Mapped[Optional[str]] = mapped_column(Text)
    name: Mapped[str] = mapped_column(Text, nullable=False)
    officer_role: Mapped[Optional[str]] = mapped_column(String(64))
    nationality: Mapped[Optional[str]] = mapped_column(Text)
    occupation: Mapped[Optional[str]] = mapped_column(Text)
    country_of_residence: Mapped[Optional[str]] = mapped_column(Text)
    # Month and year only — Companies House does not expose day of birth
    date_of_birth_month: Mapped[Optional[int]] = mapped_column(SmallInteger)
    date_of_birth_year: Mapped[Optional[int]] = mapped_column(SmallInteger)
    kind: Mapped[Optional[str]] = mapped_column(String(32))
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    appointments: Mapped[list["OfficerAppointment"]] = relationship(
        back_populates="officer", cascade="all, delete-orphan"
    )


class OfficerAppointment(Base, TimestampMixin):
    """
    A single appointment of an officer to a company.

    Unique on (company_id, officer_id, role, appointed_on) per docs/02.
    resigned_on being NULL indicates a current appointment.
    """

    __tablename__ = "officer_appointments"

    __table_args__ = (
        UniqueConstraint(
            "company_id",
            "officer_id",
            "role",
            "appointed_on",
            name="uq_officer_appointments",
        ),
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
    officer_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("officers.id", ondelete="CASCADE"),
        nullable=False,
    )
    appointment_id: Mapped[Optional[str]] = mapped_column(Text)
    role: Mapped[Optional[str]] = mapped_column(String(64))
    appointed_on: Mapped[Optional[date]] = mapped_column(Date)
    resigned_on: Mapped[Optional[date]] = mapped_column(Date)
    is_pre_1992_appointment: Mapped[Optional[bool]] = mapped_column(Boolean)
    address: Mapped[Optional[dict]] = mapped_column(JSONB)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    raw_payload: Mapped[Optional[dict]] = mapped_column(JSONB)

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="officer_appointments")
    officer: Mapped["Officer"] = relationship(back_populates="appointments")
