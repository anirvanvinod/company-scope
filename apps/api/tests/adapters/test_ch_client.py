"""
Tests for the Companies House adapter client.

All tests use respx to intercept httpx calls — no live network requests are made.
The CH_BASE_URL constant from the client module is used to build mock URLs so tests
stay aligned with the real base URL without repeating the string.

Coverage:
  - successful response parsing for all 6 endpoints
  - 404 raises CHNotFoundError
  - 429 raises CHRateLimitError (after retries exhausted)
  - 5xx raises CHUpstreamError (after retries exhausted)
  - 401 raises CHAuthError immediately (no retry)
  - API key is sent as Basic Auth username with empty password
  - extra upstream fields are ignored (extra="ignore")
  - retry reduces attempt count before final raise
"""

import httpx
import pytest
import respx
from unittest.mock import AsyncMock, patch

from ch_client.client import CH_BASE_URL, CompaniesHouseClient
from ch_client.exceptions import (
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
)
from ch_client.schemas import (
    CHChargesResponse,
    CHCompanyProfile,
    CHFilingHistoryResponse,
    CHOfficersResponse,
    CHPSCsResponse,
    CHSearchResponse,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

TEST_API_KEY = "test-api-key-do-not-use"


def _make_client(max_retries: int = 0) -> CompaniesHouseClient:
    """Create a client pointing at the real CH_BASE_URL (intercepted by respx)."""
    return CompaniesHouseClient(
        api_key=TEST_API_KEY,
        base_url=CH_BASE_URL,
        max_retries=max_retries,
    )


# ---------------------------------------------------------------------------
# Search
# ---------------------------------------------------------------------------


@respx.mock
async def test_search_companies_returns_typed_response() -> None:
    respx.get(f"{CH_BASE_URL}/search/companies").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "company_number": "12345678",
                        "title": "Acme Ltd",
                        "company_status": "active",
                        "company_type": "ltd",
                        "date_of_creation": "2010-06-01",
                        "registered_office_address": {
                            "address_line_1": "1 Test Street",
                            "locality": "London",
                            "postal_code": "EC1A 1BB",
                        },
                    }
                ],
                "total_results": 1,
                "items_per_page": 20,
                "start_index": 0,
                # extra field — must be silently ignored
                "kind": "search#companies",
            },
        )
    )
    async with _make_client() as client:
        result = await client.search_companies("Acme Ltd")

    assert isinstance(result, CHSearchResponse)
    assert len(result.items) == 1
    item = result.items[0]
    assert item.company_number == "12345678"
    assert item.title == "Acme Ltd"
    assert item.company_status == "active"
    assert result.total_results == 1


# ---------------------------------------------------------------------------
# Company profile
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_company_returns_typed_profile() -> None:
    respx.get(f"{CH_BASE_URL}/company/12345678").mock(
        return_value=httpx.Response(
            200,
            json={
                "company_number": "12345678",
                "company_name": "Acme Ltd",
                "company_status": "active",
                "type": "ltd",
                "jurisdiction": "england-wales",
                "date_of_creation": "2010-06-01",
                "has_insolvency_history": False,
                "has_charges": True,
                "sic_codes": ["62012"],
                "accounts": {
                    "next_due": "2026-01-31",
                    "overdue": False,
                    "next_made_up_to": "2025-02-28",
                },
                "confirmation_statement": {
                    "next_due": "2026-06-01",
                    "overdue": False,
                },
                "registered_office_address": {
                    "address_line_1": "1 Test Street",
                    "locality": "London",
                    "postal_code": "EC1A 1BB",
                    "country": "England",
                },
                "etag": "abcdef123456",
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_company("12345678")

    assert isinstance(result, CHCompanyProfile)
    assert result.company_number == "12345678"
    assert result.company_name == "Acme Ltd"
    assert result.type == "ltd"
    assert result.sic_codes == ["62012"]
    assert result.accounts is not None
    assert result.accounts.overdue is False
    assert result.confirmation_statement is not None


@respx.mock
async def test_get_company_ignores_unknown_upstream_fields() -> None:
    """Extra fields in the CH response must not raise a validation error."""
    respx.get(f"{CH_BASE_URL}/company/99999999").mock(
        return_value=httpx.Response(
            200,
            json={
                "company_number": "99999999",
                "company_name": "Future Fields Ltd",
                # Fields that don't exist in our schema
                "new_field_added_by_ch": "some_value",
                "another_unknown": {"nested": True},
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_company("99999999")

    assert result.company_number == "99999999"


# ---------------------------------------------------------------------------
# Filing history
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_filing_history_returns_typed_response() -> None:
    respx.get(f"{CH_BASE_URL}/company/12345678/filing-history").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "transaction_id": "MzAwOTQxNDE5OGFkaXF6a2N4",
                        "category": "accounts",
                        "type": "AA",
                        "description": "accounts-with-accounts-type-small",
                        "date": "2025-11-15",
                        "action_date": "2025-02-28",
                        "pages": 8,
                        "links": {"document_metadata": "/document/..."},
                    }
                ],
                "total_count": 1,
                "items_per_page": 100,
                "start_index": 0,
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_filing_history("12345678")

    assert isinstance(result, CHFilingHistoryResponse)
    assert len(result.items) == 1
    filing = result.items[0]
    assert filing.transaction_id == "MzAwOTQxNDE5OGFkaXF6a2N4"
    assert filing.category == "accounts"
    assert filing.type == "AA"


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_officers_returns_typed_response() -> None:
    respx.get(f"{CH_BASE_URL}/company/12345678/officers").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "name": "SMITH, Alice Jane",
                        "officer_role": "director",
                        "appointed_on": "2015-03-01",
                        "nationality": "British",
                        "occupation": "Director",
                        "country_of_residence": "England",
                        "date_of_birth": {"month": 4, "year": 1975},
                        "address": {
                            "address_line_1": "1 Test Street",
                            "locality": "London",
                            "postal_code": "EC1A 1BB",
                        },
                    }
                ],
                "active_count": 1,
                "resigned_count": 0,
                "total_results": 1,
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_officers("12345678")

    assert isinstance(result, CHOfficersResponse)
    assert len(result.items) == 1
    officer = result.items[0]
    assert officer.name == "SMITH, Alice Jane"
    assert officer.officer_role == "director"
    assert officer.date_of_birth is not None
    assert officer.date_of_birth.month == 4
    assert officer.date_of_birth.year == 1975


# ---------------------------------------------------------------------------
# PSCs
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_pscs_returns_typed_response() -> None:
    respx.get(
        f"{CH_BASE_URL}/company/12345678/persons-with-significant-control"
    ).mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "name": "Alice Smith",
                        "kind": "individual-person-with-significant-control",
                        "notified_on": "2016-04-06",
                        "natures_of_control": [
                            "ownership-of-shares-25-to-50-percent"
                        ],
                        "nationality": "British",
                        "country_of_residence": "England",
                        "date_of_birth": {"month": 4, "year": 1975},
                    }
                ],
                "active_count": 1,
                "total_results": 1,
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_pscs("12345678")

    assert isinstance(result, CHPSCsResponse)
    psc = result.items[0]
    assert psc.name == "Alice Smith"
    assert psc.natures_of_control == ["ownership-of-shares-25-to-50-percent"]


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------


@respx.mock
async def test_get_charges_returns_typed_response() -> None:
    respx.get(f"{CH_BASE_URL}/company/12345678/charges").mock(
        return_value=httpx.Response(
            200,
            json={
                "items": [
                    {
                        "charge_code": "0881860017",
                        "charge_number": 1,
                        "status": "outstanding",
                        "delivered_on": "2018-03-15",
                        "persons_entitled": [{"name": "Barclays Bank PLC"}],
                    }
                ],
                "total_count": 1,
                "satisfied_count": 0,
            },
        )
    )
    async with _make_client() as client:
        result = await client.get_charges("12345678")

    assert isinstance(result, CHChargesResponse)
    charge = result.items[0]
    assert charge.charge_code == "0881860017"
    assert charge.status == "outstanding"


# ---------------------------------------------------------------------------
# Error handling
# ---------------------------------------------------------------------------


@respx.mock
async def test_404_raises_ch_not_found_error() -> None:
    respx.get(f"{CH_BASE_URL}/company/00000000").mock(
        return_value=httpx.Response(404, json={"errors": [{"error": "company-profile-not-found"}]})
    )
    async with _make_client() as client:
        with pytest.raises(CHNotFoundError) as exc_info:
            await client.get_company("00000000")
    assert "00000000" in str(exc_info.value)


@respx.mock
async def test_401_raises_ch_auth_error_without_retry() -> None:
    """A 401 must raise immediately — never retried."""
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        return httpx.Response(401)

    respx.get(f"{CH_BASE_URL}/company/12345678").mock(side_effect=handler)

    async with _make_client(max_retries=3) as client:
        with pytest.raises(CHAuthError):
            await client.get_company("12345678")

    assert call_count == 1, "401 must not be retried"


@respx.mock
async def test_429_raises_rate_limit_error_after_retries() -> None:
    """
    A persistent 429 raises CHRateLimitError after exhausting retries.

    Uses Retry-After: 0 to avoid actually sleeping in tests.
    """
    respx.get(f"{CH_BASE_URL}/company/12345678").mock(
        return_value=httpx.Response(
            429, headers={"Retry-After": "0"}, json={}
        )
    )
    # max_retries=1 → 2 total attempts, then raises
    async with _make_client(max_retries=1) as client:
        with pytest.raises(CHRateLimitError) as exc_info:
            await client.get_company("12345678")
    assert exc_info.value.retry_after == 0


@respx.mock
async def test_5xx_raises_upstream_error_after_retries() -> None:
    """A persistent 503 raises CHUpstreamError after exhausting retries."""
    respx.get(f"{CH_BASE_URL}/company/12345678").mock(
        return_value=httpx.Response(503, text="Service Unavailable")
    )
    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with _make_client(max_retries=1) as client:
            with pytest.raises(CHUpstreamError) as exc_info:
                await client.get_company("12345678")
    assert exc_info.value.status_code == 503


@respx.mock
async def test_5xx_retries_before_success() -> None:
    """If CH returns 503 once then 200, the client recovers transparently."""
    responses = [
        httpx.Response(503, text="Service Unavailable"),
        httpx.Response(
            200,
            json={
                "company_number": "12345678",
                "company_name": "Resilient Ltd",
            },
        ),
    ]
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        resp = responses[min(call_count, len(responses) - 1)]
        call_count += 1
        return resp

    respx.get(f"{CH_BASE_URL}/company/12345678").mock(side_effect=handler)

    # max_retries=1 allows the second attempt to succeed; patch sleep for speed
    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with _make_client(max_retries=1) as client:
            result = await client.get_company("12345678")

    assert result.company_name == "Resilient Ltd"
    assert call_count == 2


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------


@respx.mock
async def test_api_key_sent_as_basic_auth_username() -> None:
    """
    The API key must be transmitted as the HTTP Basic Auth username.
    The password must be empty.
    This verifies the server-side-only auth pattern from docs/01.
    """
    captured_auth: str | None = None

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal captured_auth
        captured_auth = request.headers.get("Authorization", "")
        return httpx.Response(
            200,
            json={"company_number": "12345678", "company_name": "Auth Test Ltd"},
        )

    respx.get(f"{CH_BASE_URL}/company/12345678").mock(side_effect=handler)

    async with CompaniesHouseClient(
        api_key="my-secret-key", base_url=CH_BASE_URL
    ) as client:
        await client.get_company("12345678")

    assert captured_auth is not None
    assert captured_auth.startswith("Basic ")

    import base64
    decoded = base64.b64decode(captured_auth[len("Basic "):]).decode()
    username, _, password = decoded.partition(":")
    assert username == "my-secret-key", "API key must be the Basic Auth username"
    assert password == "", "Basic Auth password must be empty for CH API"


# ---------------------------------------------------------------------------
# Network error paths
# ---------------------------------------------------------------------------


@respx.mock
async def test_timeout_retries_then_raises_ch_request_error() -> None:
    """
    httpx.TimeoutException is retried up to max_retries times, then raises
    CHRequestError.  asyncio.sleep is patched to avoid real delays in CI.
    """
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.TimeoutException("timed out", request=request)

    respx.get(f"{CH_BASE_URL}/company/12345678").mock(side_effect=handler)

    with patch("asyncio.sleep", new_callable=AsyncMock):
        async with _make_client(max_retries=2) as client:
            with pytest.raises(CHRequestError):
                await client.get_company("12345678")

    # initial attempt + 2 retries = 3 total calls
    assert call_count == 3, "TimeoutException must be retried max_retries times"


@respx.mock
async def test_non_timeout_request_error_raises_immediately() -> None:
    """
    A non-timeout httpx.RequestError (e.g. connection refused) must raise
    CHRequestError immediately without any retry.
    """
    call_count = 0

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal call_count
        call_count += 1
        raise httpx.ConnectError("connection refused", request=request)

    respx.get(f"{CH_BASE_URL}/company/12345678").mock(side_effect=handler)

    async with _make_client(max_retries=3) as client:
        with pytest.raises(CHRequestError):
            await client.get_company("12345678")

    assert call_count == 1, "Non-timeout RequestError must not be retried"
