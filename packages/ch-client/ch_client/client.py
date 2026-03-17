"""
Companies House API client.

Architecture notes (docs/01-system-architecture.md):
  - The browser NEVER calls Companies House directly.
  - This client is used server-side only — by the API service and worker service.
  - The API key is passed via HTTP Basic Auth (key as username, empty password)
    per the Companies House REST API authentication spec.

Usage:
    async with CompaniesHouseClient(api_key="...") as client:
        profile = await client.get_company("12345678")

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

from .exceptions import (
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
    CompaniesHouseError,
)
from .schemas import (
    CHChargesResponse,
    CHCompanyProfile,
    CHDocumentMetadata,
    CHFilingHistoryResponse,
    CHOfficersResponse,
    CHPSCsResponse,
    CHSearchResponse,
)

# ---------------------------------------------------------------------------
# Module-level defaults — override at construction time for testing
# ---------------------------------------------------------------------------

CH_BASE_URL = "https://api.company-information.service.gov.uk"
CH_DOC_BASE_URL = "https://document-api.company-information.service.gov.uk"
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
        document_base_url: str = CH_DOC_BASE_URL,
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
        # Separate client for the Document API (different base URL, same auth).
        # follow_redirects=True is required: the /content endpoint issues a 302
        # redirect to a CDN where the actual document bytes are served.
        self._doc_http = httpx.AsyncClient(
            base_url=document_base_url,
            auth=(api_key, ""),
            timeout=timeout,
            follow_redirects=True,
        )

    async def __aenter__(self) -> "CompaniesHouseClient":
        return self

    async def __aexit__(self, *_: Any) -> None:
        await self._http.aclose()
        await self._doc_http.aclose()

    async def aclose(self) -> None:
        """Explicitly close the underlying HTTP clients."""
        await self._http.aclose()
        await self._doc_http.aclose()

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

            # Any other non-2xx (e.g. 400, 403, 405, 501) — surface immediately
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

    # ------------------------------------------------------------------
    # Document API methods (https://document-api.company-information.service.gov.uk)
    # ------------------------------------------------------------------

    async def _doc_get(self, path: str) -> Any:
        """
        GET from the Document API, expecting a JSON response.

        Same retry/backoff semantics as _get but uses _doc_http.
        """
        last_exc: CompaniesHouseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._doc_http.get(
                    path, headers={"Accept": "application/json"}
                )
            except httpx.TimeoutException as exc:
                last_exc = CHRequestError(
                    f"Document API request to {path!r} timed out (attempt {attempt + 1})"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc from exc
            except httpx.RequestError as exc:
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
                detail = response.text[:200] if response.text else ""
                last_exc = CHUpstreamError(response.status_code, detail)
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc
            if not response.is_success:
                raise CHUpstreamError(
                    response.status_code,
                    response.text[:200] if response.text else "",
                )
            return response.json()

        assert last_exc is not None
        raise last_exc

    async def _doc_get_bytes(self, path: str, accept: str) -> bytes:
        """
        GET from the Document API, returning raw bytes.

        Used for document content download.  The Document API typically
        responds with a 302 redirect to a CDN; _doc_http follows it
        automatically.  The Accept header tells CH which format to serve.
        """
        last_exc: CompaniesHouseError | None = None

        for attempt in range(self._max_retries + 1):
            try:
                response = await self._doc_http.get(
                    path, headers={"Accept": accept}
                )
            except httpx.TimeoutException as exc:
                last_exc = CHRequestError(
                    f"Document content request to {path!r} timed out"
                    f" (attempt {attempt + 1})"
                )
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc from exc
            except httpx.RequestError as exc:
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
                detail = response.text[:200] if response.text else ""
                last_exc = CHUpstreamError(response.status_code, detail)
                if attempt < self._max_retries:
                    await asyncio.sleep(_backoff_seconds(attempt))
                    continue
                raise last_exc
            if not response.is_success:
                raise CHUpstreamError(
                    response.status_code,
                    response.text[:200] if response.text else "",
                )
            return response.content

        assert last_exc is not None
        raise last_exc

    async def get_document_metadata(self, document_id: str) -> CHDocumentMetadata:
        """
        Fetch metadata for a CH filing document.

        GET /document/{document_id}  (Document API)

        Returns content types available, size, and other filing metadata.
        """
        data = await self._doc_get(f"/document/{document_id}")
        return CHDocumentMetadata.model_validate(data)

    async def get_document_content(
        self, document_id: str, content_type: str
    ) -> bytes:
        """
        Download the raw bytes of a CH filing document.

        GET /document/{document_id}/content  (Document API)

        content_type must be one of the types returned by get_document_metadata()
        available_content_types.  The Document API redirects to a CDN; the
        redirect is followed automatically.
        """
        return await self._doc_get_bytes(
            f"/document/{document_id}/content", accept=content_type
        )
