"""
MethodologyVersion model.

NOTE: This table is not defined in docs/02-database-schema.md. It is
introduced as an extension required by the product's methodology versioning
requirements described in docs/06-methodology.md §Methodology versioning.

See docs/decisions/001-canonical-fact-names.md for context on the broader
naming decisions that gate further methodology-linked tables.

Fields follow docs/06 §Recommended fields.
"""

import uuid
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, String, Text, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class MethodologyVersion(Base):
    """
    Registry of methodology versions.

    methodology_version strings on other tables (risk_signals,
    company_snapshots, extraction_runs) reference entries here by value.
    Foreign key enforcement is intentionally left as application-level
    until the full methodology registry design is settled.
    """

    __tablename__ = "methodology_versions"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    version: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    effective_date: Mapped[date] = mapped_column(Date, nullable=False)
    release_notes: Mapped[Optional[str]] = mapped_column(Text)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
