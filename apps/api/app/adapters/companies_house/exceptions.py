"""
Re-exports Companies House exceptions from the shared ch_client package.

Import from here within the API service, or directly from ch_client.exceptions
in service-agnostic code.
"""

from ch_client.exceptions import (  # noqa: F401
    CHAuthError,
    CHNotFoundError,
    CHRateLimitError,
    CHRequestError,
    CHUpstreamError,
    CompaniesHouseError,
)

__all__ = [
    "CompaniesHouseError",
    "CHNotFoundError",
    "CHRateLimitError",
    "CHAuthError",
    "CHUpstreamError",
    "CHRequestError",
]
