"""
RiskSignal model.

Schema source: docs/02-database-schema.md §12 risk_signals.

Signals are transparent, deterministic, rule-based findings linked to
evidence and methodology versions. They are never opaque ML scores.

Controlled vocabularies (per docs/02 §Suggested enums):
  severity: low | medium | high
  status:   active | resolved | suppressed

Every signal must store:
  - explanation (human-readable)
  - evidence (JSONB — links to source filing, date, metric value, etc.)
  - methodology_version (so signal definitions can be reviewed)
  - first_detected_at and last_confirmed_at (for timeline display)

See docs/06-methodology.md §Rule-based signal methodology for the full list
of signal categories and example rules.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID as PgUUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base, TimestampMixin

if TYPE_CHECKING:
    from app.models.company import Company


class RiskSignal(Base, TimestampMixin):
    """
    A rule-based signal attached to a company.

    Signals have a lifecycle: active → resolved (or suppressed).
    resolved_at is set when the underlying condition is no longer true.
    """

    __tablename__ = "risk_signals"

    id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    company_id: Mapped[uuid.UUID] = mapped_column(
        PgUUID(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
    )
    signal_code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    signal_name: Mapped[str] = mapped_column(Text, nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    severity: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="active")
    explanation: Mapped[str] = mapped_column(Text, nullable=False)
    evidence: Mapped[Optional[dict]] = mapped_column(JSONB)
    methodology_version: Mapped[str] = mapped_column(String(32), nullable=False)
    first_detected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    last_confirmed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True))

    # Relationships
    company: Mapped["Company"] = relationship(back_populates="risk_signals")
