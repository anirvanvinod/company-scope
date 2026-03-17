"""
Companies House client — API service shim.

Re-exports CompaniesHouseClient and CH_BASE_URL from the shared ch_client
package and adds create_ch_client(), an API-service-specific factory that
reads credentials from app.config.settings.

The browser NEVER calls Companies House directly.  This module is
server-side only.
"""

from ch_client.client import CH_BASE_URL, CompaniesHouseClient  # noqa: F401


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
