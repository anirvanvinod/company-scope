"""
companyscope-ch-client — shared Companies House API client.

Public surface:
    CompaniesHouseClient   — async client for the CH REST API and Document API
    CH_BASE_URL            — canonical CH Public Data API base URL
    CH_DOC_BASE_URL        — canonical CH Document API base URL
    CompaniesHouseError    — base exception
    CHNotFoundError        — 404
    CHRateLimitError       — 429
    CHAuthError            — 401
    CHUpstreamError        — 5xx
    CHRequestError         — network / timeout

    All response schema classes are available from ch_client.schemas.
"""

from ch_client.client import CH_BASE_URL, CH_DOC_BASE_URL, CompaniesHouseClient
from ch_client.exceptions import (
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
    CompaniesHouseError,
)

__all__ = [
    "CompaniesHouseClient",
    "CH_BASE_URL",
    "CH_DOC_BASE_URL",
    "CompaniesHouseError",
    "CHNotFoundError",
    "CHRateLimitError",
    "CHAuthError",
    "CHUpstreamError",
    "CHRequestError",
]
