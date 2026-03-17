"""
Company and CompanySnapshot models.

Schema source: docs/02-database-schema.md §1 companies, §2 company_snapshots.

company_snapshots is the denormalised read model for the UI (not source of truth).
It has a partial unique index enforcing only one current snapshot per company;
this is defined in the migration, not via __table_args__, because SQLAlchemy's
declarative Index() does not support partial index WHERE clauses portably.
"""

import uuid
from datetime import date, datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Date, DateTime, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.charge import Charge
    from app.models.filing import Filing
    from app.models.financial_fact import FinancialFact
    from app.models.financial_period import FinancialPeriod
    from app.models.insolvency import InsolvencyCase
    from app.models.officer import OfficerAppointment
    from app.models.ops import RefreshRun
    from app.models.psc import PscRecord
    from app.models.signal import RiskSignal


class Company(Base, TimestampMixin):
    """
    Canonical company identity and current profile.

    company_number is the primary business key used in all API paths.
    registered_office_address is stored as JSONB to accommodate the
    variable structure returned by Companies House.
    """

    __tablename__ = "companies"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_number: Mapped[str] = mapped_column(String(16), unique=True, nullable=False)
    company_name: Mapped[str] = mapped_column(Text, nullable=False)
    jurisdiction: Mapped[Optional[str]] = mapped_column(String(64))
    company_status: Mapped[Optional[str]] = mapped_column(String(64), index=True)
    company_type: Mapped[Optional[str]] = mapped_column(String(64))
    subtype: Mapped[Optional[str]] = mapped_column(String(64))
    date_of_creation: Mapped[Optional[date]] = mapped_column(Date)
    cessation_date: Mapped[Optional[date]] = mapped_column(Date)
    has_insolvency_history: Mapped[Optional[bool]] = mapped_column(Boolean)
    has_charges: Mapped[Optional[bool]] = mapped_column(Boolean)
    accounts_next_due: Mapped[Optional[date]] = mapped_column(Date)
    accounts_overdue: Mapped[Optional[bool]] = mapped_column(Boolean)
    confirmation_statement_next_due: Mapped[Optional[date]] = mapped_column(Date)
    confirmation_statement_overdue: Mapped[Optional[bool]] = mapped_column(Boolean)
    registered_office_address: Mapped[Optional[dict]] = mapped_column(JSONB)
    sic_codes: Mapped[Optional[list[str]]] = mapped_column(ARRAY(Text))
    source_etag: Mapped[Optional[str]] = mapped_column(Text)
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    filings: Mapped[list["Filing"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    snapshots: Mapped[list["CompanySnapshot"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    officer_appointments: Mapped[list["OfficerAppointment"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    psc_records: Mapped[list["PscRecord"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    charges: Mapped[list["Charge"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    insolvency_cases: Mapped[list["InsolvencyCase"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    risk_signals: Mapped[list["RiskSignal"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    refresh_runs: Mapped[list["RefreshRun"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    financial_periods: Mapped[list["FinancialPeriod"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )
    financial_facts: Mapped[list["FinancialFact"]] = relationship(
        back_populates="company", cascade="all, delete-orphan"
    )


class CompanySnapshot(Base):
    """
    Denormalised read model for fast company page rendering.

    This is NOT the source of truth. It is rebuilt from canonical tables
    whenever new data arrives. Only one snapshot per company may be current
    at any time; this constraint is enforced by a partial unique index in
    the migration: UNIQUE (company_id) WHERE is_current = true.

    snapshot_payload shape follows docs/02 §Snapshot payload shape recommendation.

    No updated_at: snapshots are write-once. To update, set is_current = false
    on the old row and insert a new row.
    """

    __tablename__ = "company_snapshots"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    snapshot_version: Mapped[int] = mapped_column(Integer, nullable=False)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    parser_version: Mapped[Optional[str]] = mapped_column(String(32))
    freshness_status: Mapped[str] = mapped_column(String(32), nullable=False)
    snapshot_payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    snapshot_generated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    source_last_checked_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True)
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="snapshots")
