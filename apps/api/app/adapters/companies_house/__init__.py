"""
Companies House adapter.

Public surface:
    CompaniesHouseClient   — async client for the CH REST API
    create_ch_client()     — factory that reads from app.config.settings
    CompaniesHouseError    — base exception
    CHNotFoundError        — 404
    CHRateLimitError       — 429
    CHAuthError            — 401
    CHUpstreamError        — 5xx
    CHRequestError         — network / timeout

    All response schema classes are available from
    app.adapters.companies_house.schemas if needed directly.
"""

from app.adapters.companies_house.client import CompaniesHouseClient, create_ch_client
from app.adapters.companies_house.exceptions import (
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
    CompaniesHouseError,
)

__all__ = [
    "CompaniesHouseClient",
    "create_ch_client",
    "CompaniesHouseError",
    "CHNotFoundError",
    "CHRateLimitError",
    "CHAuthError",
    "CHUpstreamError",
    "CHRequestError",
]
