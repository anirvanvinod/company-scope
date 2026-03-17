"""
Pydantic schemas for Companies House API responses.

Design rules:
- model_config extra="ignore" on every model — new upstream fields never break parsing
- Only declare fields that downstream code actually uses
- All fields are Optional unless the CH docs guarantee presence
- date fields are parsed automatically by Pydantic v2 from "YYYY-MM-DD" strings
- These are UPSTREAM response shapes — they are not the same as our ORM models
  or public API response schemas (those come later)

CH API base URL: https://api.company-information.service.gov.uk
CH API docs: https://developer-specs.company-information.service.gov.uk/
"""

from __future__ import annotations

from datetime import date
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict


class _CHBase(BaseModel):
    model_config = ConfigDict(extra="ignore", populate_by_name=True)


# ---------------------------------------------------------------------------
# Shared sub-models
# ---------------------------------------------------------------------------


class CHAddress(_CHBase):
    """Registered office or correspondence address."""

    care_of: Optional[str] = None
    premises: Optional[str] = None
    address_line_1: Optional[str] = None
    address_line_2: Optional[str] = None
    locality: Optional[str] = None
    region: Optional[str] = None
    postal_code: Optional[str] = None
    country: Optional[str] = None


class CHDateOfBirth(_CHBase):
    """
    Partial date of birth.

    CH exposes only month and year for privacy. Day is never present.
    """

    month: Optional[int] = None
    year: Optional[int] = None


# ---------------------------------------------------------------------------
# Company search  (GET /search/companies)
# ---------------------------------------------------------------------------


class CHSearchItem(_CHBase):
    """One item in a company search result list."""

    company_number: str
    title: str  # company name in search results
    company_status: Optional[str] = None
    company_type: Optional[str] = None
    date_of_creation: Optional[date] = None
    registered_office_address: Optional[CHAddress] = None
    description: Optional[str] = None


class CHSearchResponse(_CHBase):
    """Response envelope for GET /search/companies."""

    items: list[CHSearchItem] = []
    total_results: Optional[int] = None
    items_per_page: Optional[int] = None
    start_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Company profile  (GET /company/{company_number})
# ---------------------------------------------------------------------------


class CHAccountsSummary(_CHBase):
    """Accounts filing summary nested inside a company profile."""

    next_due: Optional[date] = None
    overdue: Optional[bool] = None
    next_made_up_to: Optional[date] = None


class CHConfirmationStatement(_CHBase):
    """Confirmation statement summary nested inside a company profile."""

    next_due: Optional[date] = None
    overdue: Optional[bool] = None
    next_made_up_to: Optional[date] = None
    last_made_up_to: Optional[date] = None


class CHCompanyProfile(_CHBase):
    """
    Response for GET /company/{company_number}.

    CH uses 'type' for company type and 'name' is absent at the top level
    (the company name is in 'company_name').
    """

    company_number: str
    company_name: str
    company_status: Optional[str] = None
    company_status_detail: Optional[str] = None
    type: Optional[str] = None          # CH field name for company_type
    subtype: Optional[str] = None
    jurisdiction: Optional[str] = None
    date_of_creation: Optional[date] = None
    date_of_cessation: Optional[date] = None
    has_insolvency_history: Optional[bool] = None
    has_charges: Optional[bool] = None
    registered_office_address: Optional[CHAddress] = None
    sic_codes: Optional[list[str]] = None
    accounts: Optional[CHAccountsSummary] = None
    confirmation_statement: Optional[CHConfirmationStatement] = None
    etag: Optional[str] = None


# ---------------------------------------------------------------------------
# Filing history  (GET /company/{company_number}/filing-history)
# ---------------------------------------------------------------------------


class CHFilingHistoryItem(_CHBase):
    """One filing item in the filing history list."""

    transaction_id: str
    category: Optional[str] = None
    type: Optional[str] = None
    description: Optional[str] = None
    description_values: Optional[dict[str, Any]] = None
    action_date: Optional[date] = None
    date: Optional[date] = None         # date filed
    pages: Optional[int] = None
    barcode: Optional[str] = None
    paper_filed: Optional[bool] = None
    links: Optional[dict[str, Any]] = None


class CHFilingHistoryResponse(_CHBase):
    """Response envelope for GET /company/{company_number}/filing-history."""

    items: list[CHFilingHistoryItem] = []
    filing_history_status: Optional[str] = None
    items_per_page: Optional[int] = None
    start_index: Optional[int] = None
    total_count: Optional[int] = None


# ---------------------------------------------------------------------------
# Officers  (GET /company/{company_number}/officers)
# ---------------------------------------------------------------------------


class CHOfficerItem(_CHBase):
    """One officer appointment in the officers list."""

    # CH omits 'name' for some corporate-officer entries — must be Optional
    name: Optional[str] = None
    officer_role: Optional[str] = None
    appointed_on: Optional[date] = None
    resigned_on: Optional[date] = None
    nationality: Optional[str] = None
    occupation: Optional[str] = None
    country_of_residence: Optional[str] = None
    date_of_birth: Optional[CHDateOfBirth] = None
    address: Optional[CHAddress] = None
    is_pre_1992_appointment: Optional[bool] = None
    links: Optional[dict[str, Any]] = None


class CHOfficersResponse(_CHBase):
    """Response envelope for GET /company/{company_number}/officers."""

    items: list[CHOfficerItem] = []
    active_count: Optional[int] = None
    inactive_count: Optional[int] = None
    resigned_count: Optional[int] = None
    total_results: Optional[int] = None
    items_per_page: Optional[int] = None
    start_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Persons with significant control  (GET /company/{company_number}/persons-with-significant-control)
# ---------------------------------------------------------------------------


class CHPSCItem(_CHBase):
    """One PSC record."""

    name: Optional[str] = None
    kind: Optional[str] = None
    notified_on: Optional[date] = None
    ceased_on: Optional[date] = None
    nationality: Optional[str] = None
    country_of_residence: Optional[str] = None
    date_of_birth: Optional[CHDateOfBirth] = None
    natures_of_control: Optional[list[str]] = None
    address: Optional[CHAddress] = None
    links: Optional[dict[str, Any]] = None


class CHPSCsResponse(_CHBase):
    """Response envelope for GET /company/{company_number}/persons-with-significant-control."""

    items: list[CHPSCItem] = []
    active_count: Optional[int] = None
    ceased_count: Optional[int] = None
    total_results: Optional[int] = None
    items_per_page: Optional[int] = None
    start_index: Optional[int] = None


# ---------------------------------------------------------------------------
# Charges  (GET /company/{company_number}/charges)
# ---------------------------------------------------------------------------


class CHChargeItem(_CHBase):
    """
    One registered charge.

    charge_code is the CH string identifier for the charge (e.g. "0881860017").
    charge_number is the sequential integer index (1, 2, 3 ...) — less stable.
    We store charge_code as our charge_id when available.
    """

    charge_code: Optional[str] = None
    charge_number: Optional[int] = None
    status: Optional[str] = None
    created_on: Optional[date] = None
    delivered_on: Optional[date] = None
    satisfied_on: Optional[date] = None
    persons_entitled: Optional[list[dict[str, Any]]] = None
    particulars: Optional[dict[str, Any]] = None
    links: Optional[dict[str, Any]] = None


class CHChargesResponse(_CHBase):
    """Response envelope for GET /company/{company_number}/charges."""

    items: list[CHChargeItem] = []
    part_satisfied_count: Optional[int] = None
    satisfied_count: Optional[int] = None
    total_count: Optional[int] = None
    unfiltered_count: Optional[int] = None
