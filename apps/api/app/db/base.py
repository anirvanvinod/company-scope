"""
SQLAlchemy declarative base and shared model mixins.

All ORM models inherit from Base. TimestampMixin adds the standard
created_at / updated_at pair used by most tables.

Tables that are write-once (e.g. company_snapshots, audit_events,
extraction_runs) do NOT use TimestampMixin; they define only created_at.
"""

from datetime import datetime

from sqlalchemy import DateTime, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """Shared declarative base for all CompanyScope ORM models."""

    pass


class TimestampMixin:
    """
    Adds created_at and updated_at to a model.

    Use this mixin on mutable entities. Write-once records (snapshots,
    audit events, extraction runs) should define created_at directly
    without this mixin.
    """

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )
