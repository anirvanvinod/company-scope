"""
Pydantic models for the Phase 6B AI analysis layer.

AnalysisContext   — structured input passed to the AI model (spec §Allowed inputs).
AISummaryOutput   — structured output from the AI model or template fallback.
CompanySnapshotPayload — the full JSONB payload stored in company_snapshots.

These models are pure data — no DB coupling, no Celery coupling.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# AI input models
# ---------------------------------------------------------------------------


class FactValue(BaseModel):
    value: Decimal | None = None
    confidence: Decimal = Decimal("0")
    band: str = "unavailable"


class CompanyInfo(BaseModel):
    company_number: str
    company_name: str
    company_status: str | None = None
    company_type: str | None = None
    sic_codes: list[str] = Field(default_factory=list)
    date_of_creation: str | None = None  # "YYYY-MM-DD"
    accounts_overdue: bool = False


class PrimaryPeriodInfo(BaseModel):
    period_end: str  # "YYYY-MM-DD"
    period_start: str | None = None
    accounts_type: str | None = None
    currency_code: str = "GBP"
    extraction_confidence: Decimal = Decimal("0")
    confidence_band: str = "unavailable"


class SignalInfo(BaseModel):
    signal_key: str
    severity: str
    fired: bool
    evidence_summary: str


class DataQualityInfo(BaseModel):
    facts_available_count: int = 0
    facts_total: int = 12
    primary_period_confidence_band: str = "unavailable"
    has_prior_period: bool = False
    warnings: list[str] = Field(default_factory=list)


class AnalysisContext(BaseModel):
    """
    Structured input passed to the AI model and to the template fallback.

    Constructed by context_builder.build_analysis_context().
    Never contains raw filing bytes, unstructured text, or user PII.
    """

    company: CompanyInfo
    primary_period: PrimaryPeriodInfo
    facts: dict[str, FactValue] = Field(default_factory=dict)
    derived_metrics: dict[str, FactValue] = Field(default_factory=dict)
    signals: list[SignalInfo] = Field(default_factory=list)
    data_quality: DataQualityInfo = Field(default_factory=DataQualityInfo)


# ---------------------------------------------------------------------------
# AI output models
# ---------------------------------------------------------------------------


class NarrativeParagraph(BaseModel):
    topic: str
    text: str
    confidence_note: str | None = None


class KeyObservation(BaseModel):
    observation: str
    severity: str
    evidence_ref: str


class AISummaryOutput(BaseModel):
    """
    Structured narrative summary produced by the AI model or template fallback.

    source="ai"       → produced by local inference endpoint.
    source="template" → produced by deterministic fallback.
    """

    summary_short: str
    narrative_paragraphs: list[NarrativeParagraph] = Field(default_factory=list)
    key_observations: list[KeyObservation] = Field(default_factory=list)
    data_quality_note: str | None = None
    caveats: list[str] = Field(default_factory=list)
    source: str = "ai"


# ---------------------------------------------------------------------------
# Snapshot payload model
# ---------------------------------------------------------------------------


class CompanySnapshotPayload(BaseModel):
    """
    Full read-model persisted as JSONB in company_snapshots.snapshot_payload.

    Consumed by the Phase 7 API to render the company intelligence page.
    """

    company_number: str
    analysis_context: dict[str, Any]   # AnalysisContext serialised
    ai_summary: dict[str, Any]         # AISummaryOutput serialised
    summary_source: str                # "ai" or "template"
    methodology_version: str
    model_version: str                 # AI model name, empty string for template
    financial_summary: dict[str, Any] = Field(default_factory=dict)
    active_signals: list[dict[str, Any]] = Field(default_factory=list)
