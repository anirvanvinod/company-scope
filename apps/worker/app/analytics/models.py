"""
Shared data structures for the Phase 6A analytics layer.

These are plain dataclasses — no DB coupling, no Celery coupling.
The metric and signal computation functions operate purely on these types.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class FactSnapshot:
    """
    A single canonical financial fact from one extraction period.

    value is None when the fact was not extracted or not parseable.
    confidence is the per-fact extraction confidence score (0.0–1.0).
    """

    value: Decimal | None  # None = not available; NEVER default to 0
    confidence: Decimal    # 0.0–1.0 — always present, even when value is None


@dataclass
class PeriodSnapshot:
    """
    Lightweight view of a financial_periods row used for analysis.
    """

    period_id: uuid.UUID
    period_end: date
    period_start: date | None
    extraction_confidence: Decimal
    accounts_type: str | None


@dataclass
class MetricResult:
    """
    A single derived metric.

    metric_value is None when the metric could not be computed (missing
    inputs, zero denominator, period gap, or insufficient confidence).
    confidence is None for the same reason.
    """

    metric_key: str
    metric_value: Decimal | None  # None = not computable
    unit: str                     # 'ratio', 'count', etc.
    confidence: Decimal | None    # None = not computable
    confidence_band: str          # 'high'|'medium'|'low'|'unavailable'
    warnings: list[str] = field(default_factory=list)


@dataclass
class SignalResult:
    """
    The evaluated state of a single rule-based signal.

    fired=True  → signal is currently active.
    fired=False → signal was evaluated but did not meet firing conditions.
    None (returned from signal functions, not here) → signal could not be
        evaluated due to insufficient data; DB row is not updated.
    """

    signal_code: str
    signal_name: str
    category: str    # 'financial_risk'|'filing_risk'|'data_quality'
    severity: str    # 'high'|'medium'|'low'|'informational'
    fired: bool
    explanation: str
    evidence: dict


@dataclass
class CompanyProfile:
    """
    Company profile fields needed for signal evaluation.
    """

    accounts_overdue: bool | None
    company_status: str | None
