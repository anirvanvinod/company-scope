"""
Response schemas for filings, officers, PSCs, and charges.

Used by:
  GET /api/v1/companies/{company_number}/filings
  GET /api/v1/companies/{company_number}/officers
  GET /api/v1/companies/{company_number}/psc
  GET /api/v1/companies/{company_number}/charges
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from pydantic import BaseModel


# ---------------------------------------------------------------------------
# Filings
# ---------------------------------------------------------------------------


class FilingItem(BaseModel):
    """One filing history item."""

    transaction_id: str
    category: str | None = None
    type: str | None = None
    description: str | None = None
    action_date: date | None = None
    date_filed: date | None = None
    pages: int | None = None
    paper_filed: bool | None = None
    # True if at least one FilingDocument record exists for this filing
    has_document: bool = False
    # parse_status of the most relevant document, if present
    parse_status: str | None = None
    # Original source links from Companies House (for provenance)
    source_links: dict[str, Any] | None = None


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------


class OfficerItem(BaseModel):
    """
    One officer appointment.

    resigned_on=null means the appointment is current.
    nationality and occupation are included for identity clarity,
    not for profiling purposes.
    """

    name: str
    role: str | None = None
    nationality: str | None = None
    occupation: str | None = None
    country_of_residence: str | None = None
    appointed_on: date | None = None
    resigned_on: date | None = None
    is_current: bool = False
    # Month/year only — day is withheld by Companies House
    date_of_birth_month: int | None = None
    date_of_birth_year: int | None = None


# ---------------------------------------------------------------------------
# PSC records
# ---------------------------------------------------------------------------


class PscItem(BaseModel):
    """
    One person with significant control record.

    natures_of_control contains the raw Companies House control strings
    (e.g. "ownership-of-shares-25-to-50-percent").
    ceased_on=null means the PSC relationship is current.
    """

    name: str | None = None
    kind: str | None = None
    natures_of_control: list[str] = []
    notified_on: date | None = None
    ceased_on: date | None = None
    nationality: str | None = None
    country_of_residence: str | None = None
    is_current: bool = False
    # Month/year only (privacy)
    date_of_birth_month: int | None = None
    date_of_birth_year: int | None = None


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------


class ChargeItem(BaseModel):
    """
    One registered charge.

    Charges indicate secured financing arrangements.
    Their presence is context, not automatically a risk signal
    (per docs/06-methodology.md §Charges).

    persons_entitled and particulars preserve the structured
    Companies House payload for provenance.
    """

    charge_id: str
    status: str | None = None
    delivered_on: date | None = None
    created_on: date | None = None
    resolved_on: date | None = None
    persons_entitled: list[dict[str, Any]] | None = None
    particulars: dict[str, Any] | None = None
    source_last_checked_at: datetime | None = None


# ---------------------------------------------------------------------------
# Risk signals (detail view)
# ---------------------------------------------------------------------------


class SignalItem(BaseModel):
    """
    One risk signal with full evidence and methodology provenance.

    Used by GET /api/v1/companies/{company_number}/signals.
    """

    signal_code: str
    signal_name: str
    category: str
    severity: str
    status: str
    explanation: str
    evidence: dict[str, Any] | None = None
    methodology_version: str
    first_detected_at: datetime
    last_confirmed_at: datetime
    resolved_at: datetime | None = None
