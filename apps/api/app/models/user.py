"""
User, Watchlist, and WatchlistItem models.

Schema source: docs/02-database-schema.md §14 users, §15 watchlists, §16 watchlist_items.

Note: alert_channels (§17) is deferred — not in Phase 1A scope.
Auth implementation is deferred to Phase 8 (Better Auth).
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.ops import RefreshRun


class User(Base, TimestampMixin):
    """
    Application user.

    email uses citext (case-insensitive) at the DB level — see migration.
    The SQLAlchemy model uses String; the DB enforces case-insensitivity.
    """

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    # Stored as citext in PostgreSQL (see migration). String here is correct
    # for the ORM layer; uniqueness and case-insensitivity are DB concerns.
    email: Mapped[str] = mapped_column(String(254), unique=True, nullable=False)
    display_name: Mapped[Optional[str]] = mapped_column(Text)
    auth_provider: Mapped[str] = mapped_column(String(32), nullable=False)
    auth_subject: Mapped[Optional[str]] = mapped_column(Text)
    # Populated only for auth_provider='password'; NULL for OAuth users.
    password_hash: Mapped[Optional[str]] = mapped_column(Text)

    # Relationships
    watchlists: Mapped[list["Watchlist"]] = relationship(
        back_populates="user", cascade="all, delete-orphan"
    )


class Watchlist(Base, TimestampMixin):
    """User-owned list of watched companies."""

    __tablename__ = "watchlists"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # Relationships
    user: Mapped["User"] = relationship(back_populates="watchlists")
    items: Mapped[list["WatchlistItem"]] = relationship(
        back_populates="watchlist", cascade="all, delete-orphan"
    )


class WatchlistItem(Base):
    """A single company entry within a watchlist."""

    __tablename__ = "watchlist_items"

    __table_args__ = (
        UniqueConstraint("watchlist_id", "company_id", name="uq_watchlist_items"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    watchlist_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("watchlists.id", ondelete="CASCADE"),
        nullable=False,
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    monitoring_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="active"
    )
    last_refresh_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    watchlist: Mapped["Watchlist"] = relationship(back_populates="items")
