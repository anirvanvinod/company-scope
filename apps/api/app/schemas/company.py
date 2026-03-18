"""
Company-level Pydantic response schemas.

Used by:
  GET /api/v1/search
  GET /api/v1/companies/{company_number}

All nullable fields use `T | None` and are never substituted with defaults
(null in source → null in response — per CLAUDE.md data discipline rules).
"""

from __future__ import annotations

from datetime import date, datetime
from decimal import Decimal
from typing import Any

from pydantic import BaseModel, ConfigDict


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


class SearchResultItem(BaseModel):
    """One item in the search results list."""

    model_config = ConfigDict(from_attributes=True)

    company_number: str
    company_name: str
    company_status: str | None = None
    company_type: str | None = None
    date_of_creation: date | None = None
    registered_office_address_snippet: str | None = None
    sic_codes: list[str] = []
    match_type: str  # "exact_number" | "name"


# ---------------------------------------------------------------------------
# Company identity + overview (aggregate)
# ---------------------------------------------------------------------------


class CompanyCore(BaseModel):
    """Core company identity fields — always present when company is known."""

    model_config = ConfigDict(from_attributes=True)

    company_number: str
    company_name: str
    company_status: str | None = None
    company_type: str | None = None
    subtype: str | None = None
    jurisdiction: str | None = None
    date_of_creation: date | None = None
    cessation_date: date | None = None
    has_insolvency_history: bool | None = None
    has_charges: bool | None = None
    sic_codes: list[str] = []
    registered_office_address: dict[str, Any] | None = None


class CompanyOverview(BaseModel):
    """Compliance and filing status overview."""

    accounts_next_due: date | None = None
    accounts_overdue: bool | None = None
    confirmation_statement_next_due: date | None = None
    confirmation_statement_overdue: bool | None = None


class KeyFact(BaseModel):
    """A single key financial fact for the aggregate summary."""

    value: Decimal | None = None
    unit: str | None = None


class FinancialSummary(BaseModel):
    """
    High-level financial summary for the aggregate view.

    Present when at least one qualifying financial period exists.
    Null when no financial data has been extracted yet.
    """

    latest_period_end: date | None = None
    period_start: date | None = None
    accounts_type: str | None = None
    currency_code: str | None = None
    confidence: Decimal | None = None
    confidence_band: str = "unavailable"
    # Key facts (null when not available — never zero-substituted)
    revenue: Decimal | None = None
    net_assets_liabilities: Decimal | None = None
    profit_loss_after_tax: Decimal | None = None
    average_number_of_employees: Decimal | None = None


class ActiveSignalSummary(BaseModel):
    """Compact signal representation for the aggregate view."""

    signal_code: str
    signal_name: str
    category: str
    severity: str
    explanation: str


class NarrativeParagraph(BaseModel):
    topic: str
    text: str
    confidence_note: str | None = None


class KeyObservation(BaseModel):
    observation: str
    severity: str
    evidence_ref: str


class AiNarrativeSummary(BaseModel):
    """
    AI-generated or template-generated narrative summary.

    source="ai"       — produced by local inference endpoint.
    source="template" — deterministic fallback.
    Always includes the standard platform caveat.
    """

    summary_short: str
    narrative_paragraphs: list[NarrativeParagraph] = []
    key_observations: list[KeyObservation] = []
    data_quality_note: str | None = None
    caveats: list[str] = []
    source: str  # "ai" | "template"


class Freshness(BaseModel):
    """Freshness and provenance metadata for the snapshot."""

    snapshot_generated_at: datetime | None = None
    source_last_checked_at: datetime | None = None
    freshness_status: str = "unknown"
    # "not_built" | "current" — is_current=true snapshot exists?
    snapshot_status: str = "not_built"
    methodology_version: str | None = None


class CompanyAggregate(BaseModel):
    """
    Full company aggregate response for GET /api/v1/companies/{company_number}.

    Designed to power the main company intelligence page in one round-trip.
    Sub-resource endpoints (/financials, /signals, etc.) provide deeper detail.
    """

    company: CompanyCore
    overview: CompanyOverview
    # Null when no qualifying financial period has been extracted yet
    financial_summary: FinancialSummary | None = None
    # Only fired/active signals are included here; /signals provides full history
    active_signals: list[ActiveSignalSummary] = []
    # Null when snapshot has not been built yet
    ai_summary: AiNarrativeSummary | None = None
    freshness: Freshness
