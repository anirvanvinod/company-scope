"""
Companies House API client.

Architecture notes (docs/01-system-architecture.md):
  - The browser NEVER calls Companies House directly.
  - This client is used server-side only — by the API service and worker service.
  - The API key is passed via HTTP Basic Auth (key as username, empty password)
    per the Companies House REST API authentication spec.

Usage:
    # As an async context manager (recommended — ensures the underlying
    # httpx.AsyncClient is always closed):
    async with CompaniesHouseClient(api_key=settings.ch_api_key) as client:
        profile = await client.get_company("12345678")

    # Or use the factory shorthand:
    async with create_ch_client() as client:
        results = await client.search_companies("Acme Ltd")

Retry behaviour:
  - Retries on: 429, 500, 502, 503, 504, and httpx.TimeoutException
  - Does not retry: 401, 404, other 4xx, non-timeout network errors
  - Backoff: exponential with full jitter, capped at 30 s
  - 429 responses: uses Retry-After header when present, else 60 s backoff
  - Default max_retries=3 means up to 4 total attempts (initial + 3 retries)
"""

from __future__ import annotations

import asyncio
import datetime
import random
from typing import Any

import httpx

from app.adapters.companies_house.exceptions import (
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
    CompaniesHouseError,
)
from app.adapters.companies_house.schemas import (
    CHChargesResponse,
    CHCompanyProfile,
    CHFilingHistoryResponse,
    CHOfficersResponse,
    CHPSCsResponse,
    CHSearchResponse,
)

# ---------------------------------------------------------------------------
# Module-level defaults — override at construction time for testing
# ---------------------------------------------------------------------------

CH_BASE_URL = "https://api.company-information.service.gov.uk"
CH_DEFAULT_TIMEOUT = 10.0   # seconds per request
CH_MAX_RETRIES = 3           # retries after the initial attempt

# 5xx codes that warrant an automatic retry.
# 429 is handled separately (reads Retry-After header).
# Deliberately excludes 501/505/etc. which are not transient.
_RETRYABLE_5XX = frozenset({500, 502, 503, 504})


def _parse_retry_after(header_value: str | None, default: int = 60) -> int:
    """
    Parse a Retry-After header value into an integer number of seconds.

    Handles both forms defined in RFC 9110:
      - delay-seconds  e.g. "30"
      - HTTP-date      e.g. "Wed, 21 Oct 2015 07:28:00 GMT"

    Returns *default* (60 s) if the value is absent or unparseable.
    Never returns a negative number.
    """
    if header_value is None:
        return default
    # Try the common delay-seconds form first.
    try:
        return max(0, int(header_value))
    except ValueError:
        pass
    # Fall back to HTTP-date form.
    try:
        from email.utils import parsedate_to_datetime

        dt = parsedate_to_datetime(header_value)
        now = datetime.datetime.now(datetime.timezone.utc)
        return max(0, int((dt - now).total_seconds()))
    except Exception:
        return default


def _backoff_seconds(attempt: int) -> float:
    """
    Exponential backoff with full jitter.

    attempt=0 → 0–1 s
    attempt=1 → 0–2 s
    attempt=2 → 0–4 s
    Capped at 30 s regardless of attempt count.
    """
    cap = 30.0
    return random.uniform(0, min(cap, 2.0 ** attempt))


class CompaniesHouseClient:
    """
    Async HTTP client for the Companies House REST API.

    Instantiate once per request (or share across requests in a long-lived
    service) and close with aclose() or by using as an async context manager.
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = CH_BASE_URL,
        timeout: float = CH_DEFAULT_TIMEOUT,
        max_retries: int = CH_MAX_RETRIES,
    ) -> None:
        # CH Basic Auth: API key is the username; password must be empty string.
        # The API key must never leave the server process.
        self._max_retries = max_retries
        self._http = httpx.AsyncClient(
            base_url=base_url,
            auth=(api_key, ""),
            timeout=timeout,
            headers={"Accept": "application/json"},
        )

    async def __aenter__(self) -> "CompaniesHouseClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._http.aclose()

    async def aclose(self) -> None:
        """Explicitly close the underlying HTTP client."""
        await self._http.aclose()

    # ------------------------------------------------------------------
    # Internal request primitive
    # ------------------------------------------------------------------

    async def _get(self, path: str, params: dict[str, Any] | None = None) -> Any:
        """
        Perform a GET request with retry/backoff.

        Returns the parsed JSON body on success.
        Raises a CompaniesHouseError sub-class on all failure paths.
        """
        last_exc: CompaniesHouseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._http.get(path, params=params)
            except httpx.TimeoutException as exc:
                last_exc = CHRequestError(
                    f"Request to {path!r} timed out (attempt {attempt + 1})"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc from exc
            except httpx.RequestError as exc:
                # Non-timeout network errors are not retried
                raise CHRequestError(str(exc)) from exc

            if response.status_code == 401:
                raise CHAuthError()

            if response.status_code == 404:
                raise CHNotFoundError(path)

            if response.status_code == 429:
                retry_after = _parse_retry_after(response.headers.get("Retry-After"))
                last_exc = CHRateLimitError(retry_after)
                if attempt < self._max_retries:
                    await asyncio.sleep(retry_after)
                    continue
                raise last_exc

            if response.status_code in _RETRYABLE_5XX:
                # Truncate response body for safe logging (no PII risk but prevents
                # large error strings from being stored in exception messages)
                detail = response.text[:200] if response.text else ""
                last_exc = CHUpstreamError(response.status_code, detail)
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc

            # Any other non-2xx (e.g. 400, 403, 405) — surface immediately
            if not response.is_success:
                raise CHUpstreamError(
                    response.status_code,
                    response.text[:200] if response.text else "",
                )

            return response.json()

        # Unreachable if loop logic is correct, but satisfies type checker
        assert last_exc is not None
        raise last_exc

    # ------------------------------------------------------------------
    # Public endpoint methods
    # ------------------------------------------------------------------

    async def search_companies(
        self,
        query: str,
        items_per_page: int = 20,
        start_index: int = 0,
    ) -> CHSearchResponse:
        """
        Search for companies by name or company number.

        GET /search/companies?q=...&items_per_page=...&start_index=...
        """
        data = await self._get(
            "/search/companies",
            params={
                "q": query,
                "items_per_page": items_per_page,
                "start_index": start_index,
            },
        )
        return CHSearchResponse.model_validate(data)

    async def get_company(self, company_number: str) -> CHCompanyProfile:
        """
        Fetch the full profile for a company.

        GET /company/{company_number}
        """
        data = await self._get(f"/company/{company_number}")
        return CHCompanyProfile.model_validate(data)

    async def get_filing_history(
        self,
        company_number: str,
        items_per_page: int = 100,
        start_index: int = 0,
        category: str | None = None,
    ) -> CHFilingHistoryResponse:
        """
        Fetch filing history for a company.

        GET /company/{company_number}/filing-history
        """
        params: dict[str, Any] = {
            "items_per_page": items_per_page,
            "start_index": start_index,
        }
        if category is not None:
            params["category"] = category
        data = await self._get(
            f"/company/{company_number}/filing-history", params=params
        )
        return CHFilingHistoryResponse.model_validate(data)

    async def get_officers(
        self,
        company_number: str,
        items_per_page: int = 100,
        start_index: int = 0,
    ) -> CHOfficersResponse:
        """
        Fetch the officer list for a company.

        GET /company/{company_number}/officers
        """
        data = await self._get(
            f"/company/{company_number}/officers",
            params={"items_per_page": items_per_page, "start_index": start_index},
        )
        return CHOfficersResponse.model_validate(data)

    async def get_pscs(
        self,
        company_number: str,
        items_per_page: int = 100,
        start_index: int = 0,
    ) -> CHPSCsResponse:
        """
        Fetch persons with significant control for a company.

        GET /company/{company_number}/persons-with-significant-control
        """
        data = await self._get(
            f"/company/{company_number}/persons-with-significant-control",
            params={"items_per_page": items_per_page, "start_index": start_index},
        )
        return CHPSCsResponse.model_validate(data)

    async def get_charges(
        self,
        company_number: str,
        items_per_page: int = 100,
        start_index: int = 0,
    ) -> CHChargesResponse:
        """
        Fetch registered charges for a company.

        GET /company/{company_number}/charges
        """
        data = await self._get(
            f"/company/{company_number}/charges",
            params={"items_per_page": items_per_page, "start_index": start_index},
        )
        return CHChargesResponse.model_validate(data)


# ---------------------------------------------------------------------------
# Factory
# ---------------------------------------------------------------------------


def create_ch_client() -> CompaniesHouseClient:
    """
    Create a CompaniesHouseClient from application settings.

    Use as an async context manager:
        async with create_ch_client() as client:
            ...
    """
    from app.config import settings

    return CompaniesHouseClient(
        api_key=settings.ch_api_key,
        base_url=settings.ch_base_url,
    )
