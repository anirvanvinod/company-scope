"""
Worker-side Companies House adapter factory.

Reads credentials from the worker's own settings (app.config), which are
independent of the API service settings.  The underlying CompaniesHouseClient
comes from the shared ch_client package — no dependency on apps/api.
"""

from ch_client import CompaniesHouseClient


def create_ch_client() -> CompaniesHouseClient:
    """
    Create a CompaniesHouseClient from worker settings.

    Use as an async context manager:
        async with create_ch_client() as client:
            ...
    """
    from app.config import settings

    return CompaniesHouseClient(
        api_key=settings.ch_api_key,
        base_url=settings.ch_base_url,
    )
