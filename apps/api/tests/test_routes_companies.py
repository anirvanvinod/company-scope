"""
Route-level tests for /api/v1 company endpoints.

All tests use the async_client + mock_session fixtures from conftest.py.
No live database is required — query functions are patched to return canned data.

Patch targets: app.routers.companies.<function_name>
  (the functions are imported into the router module's namespace)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

COMPANY_NUMBER = "12345678"
COMPANY_ID = uuid.UUID("aaaaaaaa-0000-0000-0000-000000000001")

_COMPANY_ROW = {
    "id": COMPANY_ID,
    "company_number": COMPANY_NUMBER,
    "company_name": "Test Co Ltd",
    "company_status": "active",
    "company_type": "ltd",
    "subtype": None,
    "jurisdiction": "england-wales",
    "date_of_creation": date(2015, 1, 1),
    "cessation_date": None,
    "has_insolvency_history": False,
    "has_charges": False,
    "accounts_next_due": date(2025, 9, 30),
    "accounts_overdue": False,
    "confirmation_statement_next_due": date(2025, 6, 1),
    "confirmation_statement_overdue": False,
    "registered_office_address": {"locality": "London", "postal_code": "EC1A 1BB"},
    "sic_codes": ["62012"],
    "source_last_checked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
}

_SNAPSHOT_ROW = {
    "id": uuid.uuid4(),
    "snapshot_payload": {
        "summary_source": "template",
        "ai_summary": {
            "summary_short": "Test company with solid financials.",
            "narrative_paragraphs": [
                {"topic": "overview", "text": "The company is active.", "confidence_note": None}
            ],
            "key_observations": [
                {"observation": "Revenue is growing.", "severity": "low", "evidence_ref": "revenue"}
            ],
            "data_quality_note": None,
            "caveats": ["This is not investment advice."],
        },
        "active_signals": [
            {
                "signal_code": "LATE_ACCOUNTS",
                "signal_name": "Late Accounts",
                "category": "compliance",
                "severity": "high",
                "explanation": "Accounts overdue by 30 days.",
            }
        ],
        "financial_summary": {
            "latest_period_end": "2023-12-31",
            "period_start": "2023-01-01",
            "accounts_type": "full",
            "currency_code": "GBP",
            "confidence": "0.90",
            "confidence_band": "high",
            "revenue": "1000000",
            "net_assets_liabilities": "250000",
            "profit_loss_after_tax": "50000",
            "average_number_of_employees": "12",
        },
    },
    "snapshot_generated_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
    "source_last_checked_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
    "freshness_status": "current",
    "methodology_version": "v1.0",
    "is_current": True,
}

PERIOD_ID = uuid.UUID("bbbbbbbb-0000-0000-0000-000000000001")

_PERIOD_ROW = {
    "id": PERIOD_ID,
    "period_end": date(2023, 12, 31),
    "period_start": date(2023, 1, 1),
    "accounts_type": "full",
    "currency_code": "GBP",
    "extraction_confidence": Decimal("0.90"),
    "is_restated": False,
    "filing_id": uuid.uuid4(),
}

_FACT_ROWS = [
    {
        "fact_name": "revenue",
        "fact_value": Decimal("1000000"),
        "unit": "GBP",
        "raw_label": "Turnover",
        "extraction_method": "xbrl",
        "extraction_confidence": Decimal("0.95"),
        "is_derived": False,
    },
    {
        "fact_name": "net_assets_liabilities",
        "fact_value": Decimal("250000"),
        "unit": "GBP",
        "raw_label": "Net assets",
        "extraction_method": "xbrl",
        "extraction_confidence": Decimal("0.90"),
        "is_derived": False,
    },
]

_METRIC_ROWS = [
    {
        "metric_key": "current_ratio",
        "metric_value": Decimal("1.5"),
        "unit": "ratio",
        "confidence": Decimal("0.88"),
        "confidence_band": "high",
        "warnings": [],
    }
]

_SIGNAL_ROWS = [
    {
        "signal_code": "LATE_ACCOUNTS",
        "signal_name": "Late Accounts",
        "category": "compliance",
        "severity": "high",
        "status": "active",
        "explanation": "Accounts overdue by 30 days.",
        "evidence": {"days_overdue": 30},
        "methodology_version": "v1.0",
        "first_detected_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
        "last_confirmed_at": datetime(2024, 6, 1, tzinfo=timezone.utc),
        "resolved_at": None,
    }
]

_FILING_ROWS = [
    {
        "id": uuid.uuid4(),
        "transaction_id": "MzAxNzQ5NjI4OWFkaXF6a2N4",
        "category": "accounts",
        "type": "AA",
        "description": "Annual accounts",
        "action_date": date(2023, 12, 31),
        "date_filed": date(2024, 3, 15),
        "pages": 12,
        "paper_filed": False,
        "source_links": {"document": "/document/123"},
        "has_document": True,
        "parse_status": "done",
    }
]

_OFFICER_ROWS = [
    {
        "name": "Jane Smith",
        "role": "director",
        "nationality": "British",
        "occupation": "Software Engineer",
        "country_of_residence": "England",
        "appointed_on": date(2015, 1, 1),
        "resigned_on": None,
        "is_current": True,
        "date_of_birth_month": 4,
        "date_of_birth_year": 1980,
    }
]

_PSC_ROWS = [
    {
        "name": "John Doe",
        "kind": "individual-person-with-significant-control",
        "natures_of_control": ["ownership-of-shares-75-to-100-percent"],
        "notified_on": date(2015, 1, 1),
        "ceased_on": None,
        "nationality": "British",
        "country_of_residence": "England",
        "is_current": True,
        "date_of_birth_month": 7,
        "date_of_birth_year": 1975,
    }
]

_CHARGE_ROWS = [
    {
        "charge_id": "CHG001",
        "status": "outstanding",
        "delivered_on": date(2020, 6, 1),
        "created_on": date(2020, 5, 15),
        "resolved_on": None,
        "persons_entitled": [{"name": "Barclays Bank PLC"}],
        "particulars": {"type": "fixed-floating-charge"},
        "source_last_checked_at": datetime(2024, 1, 1, tzinfo=timezone.utc),
    }
]


# ---------------------------------------------------------------------------
# /search
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_returns_results(async_client):
    with patch(
        "app.routers.companies.search_companies",
        new_callable=AsyncMock,
        return_value=[_COMPANY_ROW],
    ):
        resp = await async_client.get("/api/v1/search?q=Test+Co")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["data"]) == 1
    item = body["data"][0]
    assert item["company_number"] == COMPANY_NUMBER
    assert item["match_type"] == "name"
    assert item["registered_office_address_snippet"] == "London, EC1A 1BB"


@pytest.mark.asyncio
async def test_search_exact_number_match_type(async_client):
    with patch(
        "app.routers.companies.search_companies",
        new_callable=AsyncMock,
        return_value=[_COMPANY_ROW],
    ):
        resp = await async_client.get(f"/api/v1/search?q={COMPANY_NUMBER}")

    assert resp.status_code == 200
    item = resp.json()["data"][0]
    assert item["match_type"] == "exact_number"


@pytest.mark.asyncio
async def test_search_empty_results(async_client):
    with patch(
        "app.routers.companies.search_companies",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await async_client.get("/api/v1/search?q=noresults")

    assert resp.status_code == 200
    assert resp.json()["data"] == []


@pytest.mark.asyncio
async def test_search_q_too_short(async_client):
    resp = await async_client.get("/api/v1/search?q=x")
    assert resp.status_code == 422  # FastAPI validation


# ---------------------------------------------------------------------------
# /companies/{company_number}  — aggregate
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_company_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "not_found"
    assert body["data"] is None


@pytest.mark.asyncio
async def test_get_company_with_snapshot(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_current_snapshot",
            new_callable=AsyncMock,
            return_value=_SNAPSHOT_ROW,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}")

    assert resp.status_code == 200
    body = resp.json()
    data = body["data"]

    assert data["company"]["company_number"] == COMPANY_NUMBER
    assert data["company"]["company_name"] == "Test Co Ltd"
    assert data["freshness"]["snapshot_status"] == "current"
    assert data["freshness"]["freshness_status"] == "current"
    assert data["ai_summary"]["source"] == "template"
    assert len(data["active_signals"]) == 1
    assert data["active_signals"][0]["signal_code"] == "LATE_ACCOUNTS"
    assert data["financial_summary"]["confidence_band"] == "high"


@pytest.mark.asyncio
async def test_get_company_no_snapshot(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_current_snapshot",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["freshness"]["snapshot_status"] == "not_built"
    assert data["ai_summary"] is None
    assert data["financial_summary"] is None
    assert data["active_signals"] == []


@pytest.mark.asyncio
async def test_get_company_envelope_shape(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_current_snapshot",
            new_callable=AsyncMock,
            return_value=None,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}")

    body = resp.json()
    assert "data" in body
    assert "meta" in body
    assert "error" in body
    assert body["error"] is None
    assert "request_id" in body["meta"]
    assert "generated_at" in body["meta"]


# ---------------------------------------------------------------------------
# /companies/{company_number}/financials
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_financials_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/financials")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_financials_no_periods(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_financial_periods",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/financials")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["periods"] == []
    assert data["data_quality"]["message"] == "No financial periods available"


@pytest.mark.asyncio
async def test_financials_with_data(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_financial_periods",
            new_callable=AsyncMock,
            return_value=[_PERIOD_ROW],
        ),
        patch(
            "app.routers.companies.get_facts_for_period",
            new_callable=AsyncMock,
            return_value=_FACT_ROWS,
        ),
        patch(
            "app.routers.companies.get_derived_metrics_for_period",
            new_callable=AsyncMock,
            return_value=_METRIC_ROWS,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/financials")

    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["periods"]) == 1
    period = data["periods"][0]
    assert period["period_end"] == "2023-12-31"
    assert period["confidence_band"] == "high"
    assert "revenue" in period["facts"]
    assert period["facts"]["revenue"]["value"] == "1000000"
    assert period["facts"]["revenue"]["confidence_band"] == "high"

    assert "current_ratio" in data["derived_metrics"]
    assert data["derived_metrics"]["current_ratio"]["value"] == "1.5"

    assert "revenue" in data["series"]
    assert data["series"]["revenue"][0]["period_end"] == "2023-12-31"

    dq = data["data_quality"]
    assert dq["periods_available"] == 1
    assert dq["primary_period_facts_available"] == 2
    assert dq["primary_period_confidence_band"] == "high"


@pytest.mark.asyncio
async def test_financials_null_fact_value_preserved(async_client):
    """Null fact values must not be zero-substituted."""
    null_fact_row = {
        "fact_name": "revenue",
        "fact_value": None,
        "unit": "GBP",
        "raw_label": "Turnover",
        "extraction_method": "xbrl",
        "extraction_confidence": Decimal("0.50"),
        "is_derived": False,
    }
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_financial_periods",
            new_callable=AsyncMock,
            return_value=[_PERIOD_ROW],
        ),
        patch(
            "app.routers.companies.get_facts_for_period",
            new_callable=AsyncMock,
            return_value=[null_fact_row],
        ),
        patch(
            "app.routers.companies.get_derived_metrics_for_period",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/financials")

    data = resp.json()["data"]
    assert data["periods"][0]["facts"]["revenue"]["value"] is None


# ---------------------------------------------------------------------------
# /companies/{company_number}/signals
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_signals_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/signals")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_signals_returns_list(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_risk_signals",
            new_callable=AsyncMock,
            return_value=_SIGNAL_ROWS,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/signals")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["signal_code"] == "LATE_ACCOUNTS"
    assert data[0]["severity"] == "high"
    assert data[0]["evidence"]["days_overdue"] == 30


@pytest.mark.asyncio
async def test_signals_bad_status_param(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=_COMPANY_ROW,
    ):
        resp = await async_client.get(
            f"/api/v1/companies/{COMPANY_NUMBER}/signals?status=invalid"
        )

    assert resp.status_code == 400
    assert resp.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_signals_empty(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_risk_signals",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/signals")

    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# /companies/{company_number}/filings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filings_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/filings")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_filings_returns_list(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_filings",
            new_callable=AsyncMock,
            return_value=(_FILING_ROWS, None),
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/filings")

    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 1
    f = body["data"][0]
    assert f["transaction_id"] == "MzAxNzQ5NjI4OWFkaXF6a2N4"
    assert f["category"] == "accounts"
    assert f["has_document"] is True
    assert body["meta"]["pagination"]["next_cursor"] is None


@pytest.mark.asyncio
async def test_filings_cursor_pagination(async_client):
    next_cursor = "eyJkIjogIjIwMjQtMDMtMTUiLCAiaSI6ICIxMjMifQ=="
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_filings",
            new_callable=AsyncMock,
            return_value=(_FILING_ROWS, next_cursor),
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/filings")

    body = resp.json()
    assert body["meta"]["pagination"]["next_cursor"] == next_cursor


# ---------------------------------------------------------------------------
# /companies/{company_number}/officers
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_officers_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/officers")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_officers_returns_list(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_officers",
            new_callable=AsyncMock,
            return_value=_OFFICER_ROWS,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/officers")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["name"] == "Jane Smith"
    assert data[0]["is_current"] is True
    assert data[0]["date_of_birth_year"] == 1980


@pytest.mark.asyncio
async def test_officers_bad_status_param(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=_COMPANY_ROW,
    ):
        resp = await async_client.get(
            f"/api/v1/companies/{COMPANY_NUMBER}/officers?status=wrong"
        )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /companies/{company_number}/psc
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_psc_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/psc")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_psc_returns_list(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_psc_records",
            new_callable=AsyncMock,
            return_value=_PSC_ROWS,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/psc")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    p = data[0]
    assert p["name"] == "John Doe"
    assert p["natures_of_control"] == ["ownership-of-shares-75-to-100-percent"]
    assert p["is_current"] is True


@pytest.mark.asyncio
async def test_psc_bad_status_param(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=_COMPANY_ROW,
    ):
        resp = await async_client.get(
            f"/api/v1/companies/{COMPANY_NUMBER}/psc?status=nope"
        )

    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# /companies/{company_number}/charges
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_charges_not_found(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.get("/api/v1/companies/00000000/charges")

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_charges_returns_list(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_charges",
            new_callable=AsyncMock,
            return_value=_CHARGE_ROWS,
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/charges")

    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data) == 1
    c = data[0]
    assert c["charge_id"] == "CHG001"
    assert c["status"] == "outstanding"
    assert c["persons_entitled"][0]["name"] == "Barclays Bank PLC"


@pytest.mark.asyncio
async def test_charges_bad_status_param(async_client):
    with patch(
        "app.routers.companies.get_company_by_number",
        new_callable=AsyncMock,
        return_value=_COMPANY_ROW,
    ):
        resp = await async_client.get(
            f"/api/v1/companies/{COMPANY_NUMBER}/charges?status=unknown"
        )

    assert resp.status_code == 400


@pytest.mark.asyncio
async def test_charges_empty(async_client):
    with (
        patch(
            "app.routers.companies.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.companies.get_charges",
            new_callable=AsyncMock,
            return_value=[],
        ),
    ):
        resp = await async_client.get(f"/api/v1/companies/{COMPANY_NUMBER}/charges")

    assert resp.status_code == 200
    assert resp.json()["data"] == []
