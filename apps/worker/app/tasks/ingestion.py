"""
Ingestion Celery tasks.

Five tasks are defined:

  refresh_company(company_number)
    Full refresh — fetches and upserts all 5 entity types in a single DB
    transaction.  This is the primary entry point for on-demand and scheduled
    refreshes.

  fetch_filings(company_number)
  fetch_officers(company_number)
  fetch_pscs(company_number)
  fetch_charges(company_number)
    Partial refreshes that update a single entity type.  Require the company
    to already exist in the DB (look up company_id by company_number).
    Used when only a targeted refresh is needed.

Each Celery task is synchronous and delegates to an underlying async
implementation via asyncio.run().  This is the standard pattern for
integrating async code with Celery's synchronous task executor.

Pagination is handled by _paginate() — a generic helper that loops over
start_index until all items are retrieved.

The orchestration is intentionally kept flat (no Celery sub-task chaining)
so the parser and document-fetch stages can be wired in later without
restructuring this module.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import sqlalchemy as sa

from ch_client.exceptions import CHAuthError, CHNotFoundError
from app.adapters.companies_house import create_ch_client
from app.db import get_session
from app.main import celery_app
from app.repositories import (
    create_refresh_run,
    finish_refresh_run,
    upsert_charges,
    upsert_company,
    upsert_filings,
    upsert_officers,
    upsert_pscs,
)

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Pagination helper
# ---------------------------------------------------------------------------


async def _paginate(fetch_fn: Any, *args: Any, total_attr: str, per_page: int = 100, **kwargs: Any) -> list[Any]:
    """
    Collect all pages from a paginated CH list endpoint.

    fetch_fn must accept items_per_page= and start_index= kwargs and return a
    response object with .items (list) and a total count attribute named by
    total_attr.
    """
    items: list[Any] = []
    start = 0
    while True:
        resp = await fetch_fn(
            *args, items_per_page=per_page, start_index=start, **kwargs
        )
        items.extend(resp.items)
        total = getattr(resp, total_attr, None)
        start += per_page
        if not resp.items or (total is not None and start >= total):
            break
    return items


# ---------------------------------------------------------------------------
# Company lookup helper (used by partial-refresh sub-tasks)
# ---------------------------------------------------------------------------


async def _get_company_id_or_raise(session: Any, company_number: str) -> Any:
    """Return the DB UUID for company_number, or raise ValueError if missing."""
    result = await session.execute(
        sa.text("SELECT id FROM companies WHERE company_number = :cn"),
        {"cn": company_number},
    )
    company_id = result.scalar_one_or_none()
    if company_id is None:
        raise ValueError(
            f"Company {company_number!r} not found in DB. "
            "Run refresh_company first to create the canonical record."
        )
    return company_id


# ---------------------------------------------------------------------------
# Async implementations (called by Celery tasks via asyncio.run)
# ---------------------------------------------------------------------------


async def _refresh_company_async(company_number: str) -> dict[str, Any]:
    """
    Full company refresh — all 5 entity types in one DB transaction.

    A refresh_runs row is created before work begins (status='running') and
    updated on completion or failure using an independent session so the audit
    record persists even if the main transaction rolls back.

    Returns a summary dict with entity counts for logging / result inspection.
    """
    run_id: uuid.UUID | None = None
    try:
        run_id = await create_refresh_run(None, "full")

        async with create_ch_client() as client:
            async with get_session() as session:
                # 1. Company profile (single resource — no pagination)
                profile = await client.get_company(company_number)
                company_id = await upsert_company(session, profile)
                log.info("Upserted company %s → id=%s", company_number, company_id)

                # 2. Filing history
                filings = await _paginate(
                    client.get_filing_history,
                    company_number,
                    total_attr="total_count",
                )
                filing_ids = await upsert_filings(session, company_id, filings)
                log.info("Upserted %d filings for %s", len(filing_ids), company_number)

                # 3. Officers
                officers = await _paginate(
                    client.get_officers,
                    company_number,
                    total_attr="total_results",
                )
                await upsert_officers(session, company_id, officers)
                log.info("Upserted %d officers for %s", len(officers), company_number)

                # 4. PSCs
                pscs = await _paginate(
                    client.get_pscs,
                    company_number,
                    total_attr="total_results",
                )
                await upsert_pscs(session, company_id, pscs)
                log.info("Upserted %d PSCs for %s", len(pscs), company_number)

                # 5. Charges
                charges = await _paginate(
                    client.get_charges,
                    company_number,
                    total_attr="total_count",
                )
                await upsert_charges(session, company_id, charges)
                log.info("Upserted %d charges for %s", len(charges), company_number)

                await session.commit()

        summary = {
            "company_number": company_number,
            "company_id": str(company_id),
            "filings": len(filings),
            "officers": len(officers),
            "pscs": len(pscs),
            "charges": len(charges),
        }
        await finish_refresh_run(run_id, "completed")
        return summary

    except Exception as exc:
        if run_id is not None:
            await finish_refresh_run(run_id, "failed", error_summary=str(exc)[:500])
        raise


async def _fetch_filings_async(company_number: str) -> dict[str, Any]:
    run_id: uuid.UUID | None = None
    try:
        async with create_ch_client() as client:
            async with get_session() as session:
                company_id = await _get_company_id_or_raise(session, company_number)
                run_id = await create_refresh_run(company_id, "filings")
                filings = await _paginate(
                    client.get_filing_history,
                    company_number,
                    total_attr="total_count",
                )
                filing_ids = await upsert_filings(session, company_id, filings)
                await session.commit()
        await finish_refresh_run(run_id, "completed")
        return {"company_number": company_number, "filings": len(filing_ids)}
    except Exception as exc:
        if run_id is not None:
            await finish_refresh_run(run_id, "failed", error_summary=str(exc)[:500])
        raise


async def _fetch_officers_async(company_number: str) -> dict[str, Any]:
    run_id: uuid.UUID | None = None
    try:
        async with create_ch_client() as client:
            async with get_session() as session:
                company_id = await _get_company_id_or_raise(session, company_number)
                run_id = await create_refresh_run(company_id, "officers")
                officers = await _paginate(
                    client.get_officers,
                    company_number,
                    total_attr="total_results",
                )
                await upsert_officers(session, company_id, officers)
                await session.commit()
        await finish_refresh_run(run_id, "completed")
        return {"company_number": company_number, "officers": len(officers)}
    except Exception as exc:
        if run_id is not None:
            await finish_refresh_run(run_id, "failed", error_summary=str(exc)[:500])
        raise


async def _fetch_pscs_async(company_number: str) -> dict[str, Any]:
    run_id: uuid.UUID | None = None
    try:
        async with create_ch_client() as client:
            async with get_session() as session:
                company_id = await _get_company_id_or_raise(session, company_number)
                run_id = await create_refresh_run(company_id, "pscs")
                pscs = await _paginate(
                    client.get_pscs,
                    company_number,
                    total_attr="total_results",
                )
                await upsert_pscs(session, company_id, pscs)
                await session.commit()
        await finish_refresh_run(run_id, "completed")
        return {"company_number": company_number, "pscs": len(pscs)}
    except Exception as exc:
        if run_id is not None:
            await finish_refresh_run(run_id, "failed", error_summary=str(exc)[:500])
        raise


async def _fetch_charges_async(company_number: str) -> dict[str, Any]:
    run_id: uuid.UUID | None = None
    try:
        async with create_ch_client() as client:
            async with get_session() as session:
                company_id = await _get_company_id_or_raise(session, company_number)
                run_id = await create_refresh_run(company_id, "charges")
                charges = await _paginate(
                    client.get_charges,
                    company_number,
                    total_attr="total_count",
                )
                await upsert_charges(session, company_id, charges)
                await session.commit()
        await finish_refresh_run(run_id, "completed")
        return {"company_number": company_number, "charges": len(charges)}
    except Exception as exc:
        if run_id is not None:
            await finish_refresh_run(run_id, "failed", error_summary=str(exc)[:500])
        raise


# ---------------------------------------------------------------------------
# Celery task definitions
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="ingestion.refresh_company",
    queue="company_refresh",
    max_retries=3,
    default_retry_delay=60,
)
def refresh_company(self: Any, company_number: str) -> dict[str, Any]:
    """
    Full refresh of all core upstream data for a company.

    Fetches profile, filing history, officers, PSCs, and charges from
    Companies House and upserts them into the canonical DB.
    """
    try:
        return asyncio.run(_refresh_company_async(company_number))
    except (CHAuthError, CHNotFoundError):
        raise  # non-retryable: auth failure or company not found upstream
    except Exception as exc:
        log.exception("refresh_company failed for %s: %s", company_number, exc)
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="ingestion.fetch_filings",
    queue="company_refresh",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_filings(self: Any, company_number: str) -> dict[str, Any]:
    """Refresh filing history only. Company must already exist in the DB."""
    try:
        return asyncio.run(_fetch_filings_async(company_number))
    except ValueError:
        raise  # company not found — don't retry
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="ingestion.fetch_officers",
    queue="company_refresh",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_officers(self: Any, company_number: str) -> dict[str, Any]:
    """Refresh officer list only. Company must already exist in the DB."""
    try:
        return asyncio.run(_fetch_officers_async(company_number))
    except ValueError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="ingestion.fetch_pscs",
    queue="company_refresh",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_pscs(self: Any, company_number: str) -> dict[str, Any]:
    """Refresh PSC list only. Company must already exist in the DB."""
    try:
        return asyncio.run(_fetch_pscs_async(company_number))
    except ValueError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)


@celery_app.task(
    bind=True,
    name="ingestion.fetch_charges",
    queue="company_refresh",
    max_retries=3,
    default_retry_delay=60,
)
def fetch_charges(self: Any, company_number: str) -> dict[str, Any]:
    """Refresh charges only. Company must already exist in the DB."""
    try:
        return asyncio.run(_fetch_charges_async(company_number))
    except ValueError:
        raise
    except Exception as exc:
        raise self.retry(exc=exc)
