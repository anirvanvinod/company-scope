"""
Financial response schemas.

Used by GET /api/v1/companies/{company_number}/financials.

Confidence band thresholds (per docs/05-parser-design.md §Confidence scoring):
  high        >= 0.85
  medium      >= 0.65
  low         >= 0.40
  unavailable  < 0.40  (or null)
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Confidence utility
# ---------------------------------------------------------------------------


def confidence_band(score: Decimal | None) -> str:
    """Return the display band for a 0–1 confidence score."""
    if score is None:
        return "unavailable"
    if score >= Decimal("0.85"):
        return "high"
    if score >= Decimal("0.65"):
        return "medium"
    if score >= Decimal("0.40"):
        return "low"
    return "unavailable"


# ---------------------------------------------------------------------------
# Fact detail
# ---------------------------------------------------------------------------


class FactDetail(BaseModel):
    """
    A single extracted financial fact with full provenance.

    value is null when the fact was not extractable.  Never zero-substituted.
    raw_label preserves the text label from the source document.
    """

    value: Decimal | None = None
    unit: str | None = None
    confidence: Decimal | None = None
    confidence_band: str = "unavailable"
    raw_label: str | None = None
    extraction_method: str | None = None
    is_derived: bool = False


# ---------------------------------------------------------------------------
# Period + facts
# ---------------------------------------------------------------------------


class PeriodFacts(BaseModel):
    """
    One financial reporting period with all extracted facts.

    facts maps canonical fact name → FactDetail.
    Any of the 12 canonical facts may be absent (key missing from dict)
    or present with value=null if the fact was attempted but not parseable.
    """

    period_id: uuid.UUID
    period_end: date
    period_start: date | None = None
    accounts_type: str | None = None
    currency_code: str | None = None
    extraction_confidence: Decimal | None = None
    confidence_band: str = "unavailable"
    facts: dict[str, FactDetail] = {}


# ---------------------------------------------------------------------------
# Derived metric
# ---------------------------------------------------------------------------


class MetricDetail(BaseModel):
    """
    A single derived metric (computed from facts per methodology spec).

    value is null when the metric could not be computed (missing inputs,
    zero denominator, period gap, or insufficient confidence).
    """

    value: Decimal | None = None
    unit: str = "ratio"
    confidence: Decimal | None = None
    confidence_band: str = "unavailable"
    warnings: list[str] = []


# ---------------------------------------------------------------------------
# Financial series point (for charting)
# ---------------------------------------------------------------------------


class SeriesPoint(BaseModel):
    period_end: date
    value: Decimal | None = None
    confidence_band: str = "unavailable"


# ---------------------------------------------------------------------------
# Full financials response
# ---------------------------------------------------------------------------


class FinancialsResponse(BaseModel):
    """
    Full financial response for GET /api/v1/companies/{company_number}/financials.

    periods: up to N periods (default 5), newest first.
    derived_metrics: computed metrics for the most recent (primary) period.
    series: per-fact time series across all returned periods (for charting).
    data_quality: overall quality indicators and extraction warnings.
    """

    periods: list[PeriodFacts] = []
    derived_metrics: dict[str, MetricDetail] = {}
    series: dict[str, list[SeriesPoint]] = {}
    data_quality: dict = {}
