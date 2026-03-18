"""
Read-only DB query functions for the Phase 7A public API.

All functions accept an AsyncSession and return plain dicts (via
result.mappings()) or None.  No ORM loading — consistent with the worker's
raw-SQL approach.

None of these functions commit or mutate any state.
"""

from __future__ import annotations

import base64
import json
import uuid
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Company
# ---------------------------------------------------------------------------


async def get_company_by_number(
    session: AsyncSession,
    company_number: str,
) -> dict[str, Any] | None:
    """Return the companies row for a given company_number, or None."""
    result = await session.execute(
        sa.text(
            """
            SELECT id, company_number, company_name, jurisdiction,
                   company_status, company_type, subtype,
                   date_of_creation, cessation_date,
                   has_insolvency_history, has_charges,
                   accounts_next_due, accounts_overdue,
                   confirmation_statement_next_due,
                   confirmation_statement_overdue,
                   registered_office_address, sic_codes,
                   source_last_checked_at
            FROM   companies
            WHERE  company_number = :cn
            """
        ),
        {"cn": company_number},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def search_companies(
    session: AsyncSession,
    q: str,
    limit: int = 10,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Search companies by name (ILIKE) or exact company number.

    Returns results ordered: exact number match first, then name matches
    sorted by company_name ascending.
    """
    params: dict[str, Any] = {"q": q.strip(), "limit": limit}
    status_clause = ""
    if status:
        status_clause = "AND company_status = :status"
        params["status"] = status

    result = await session.execute(
        sa.text(
            f"""
            SELECT company_number, company_name, company_status, company_type,
                   date_of_creation, registered_office_address, sic_codes,
                   CASE WHEN company_number = :q THEN 0 ELSE 1 END AS _rank
            FROM   companies
            WHERE  (
                       company_number = :q
                   OR  company_name ILIKE '%' || :q || '%'
                   )
                   {status_clause}
            ORDER  BY _rank, company_name
            LIMIT  :limit
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# Snapshot
# ---------------------------------------------------------------------------


async def get_current_snapshot(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> dict[str, Any] | None:
    """
    Return the current snapshot row for a company, or None.

    snapshot_payload is the full JSONB blob; the caller unpacks it.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT id, snapshot_payload, snapshot_generated_at,
                   source_last_checked_at, freshness_status,
                   methodology_version, is_current
            FROM   company_snapshots
            WHERE  company_id = :cid
              AND  is_current  = true
            LIMIT  1
            """
        ),
        {"cid": str(company_id)},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


# ---------------------------------------------------------------------------
# Financial periods + facts
# ---------------------------------------------------------------------------


async def get_financial_periods(
    session: AsyncSession,
    company_id: uuid.UUID,
    num_periods: int = 5,
) -> list[dict[str, Any]]:
    """
    Return up to num_periods non-restated financial periods for a company,
    ordered newest first.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT id, period_end, period_start, accounts_type,
                   currency_code, extraction_confidence, is_restated,
                   filing_id
            FROM   financial_periods
            WHERE  company_id  = :cid
              AND  is_restated = false
            ORDER  BY period_end DESC
            LIMIT  :n
            """
        ),
        {"cid": str(company_id), "n": num_periods},
    )
    return [dict(r) for r in result.mappings()]


async def get_facts_for_period(
    session: AsyncSession,
    period_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Return all financial facts for a given period_id."""
    result = await session.execute(
        sa.text(
            """
            SELECT fact_name, fact_value, unit, raw_label,
                   extraction_method, extraction_confidence, is_derived
            FROM   financial_facts
            WHERE  financial_period_id = :pid
            """
        ),
        {"pid": str(period_id)},
    )
    return [dict(r) for r in result.mappings()]


async def get_derived_metrics_for_period(
    session: AsyncSession,
    company_id: uuid.UUID,
    period_id: uuid.UUID,
) -> list[dict[str, Any]]:
    """Return derived metrics for the primary period."""
    result = await session.execute(
        sa.text(
            """
            SELECT metric_key, metric_value, unit, confidence,
                   confidence_band, warnings
            FROM   derived_metrics
            WHERE  company_id          = :cid
              AND  financial_period_id = :pid
            """
        ),
        {"cid": str(company_id), "pid": str(period_id)},
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# Signals
# ---------------------------------------------------------------------------


async def get_risk_signals(
    session: AsyncSession,
    company_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return risk signals for a company.

    status filter: "active" | "resolved" | "all" (default "all").
    """
    params: dict[str, Any] = {"cid": str(company_id)}
    status_clause = ""
    if status and status != "all":
        status_clause = "AND status = :status"
        params["status"] = status

    result = await session.execute(
        sa.text(
            f"""
            SELECT signal_code, signal_name, category, severity, status,
                   explanation, evidence, methodology_version,
                   first_detected_at, last_confirmed_at, resolved_at
            FROM   risk_signals
            WHERE  company_id = :cid
                   {status_clause}
            ORDER  BY
                   CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2
                                 WHEN 'low' THEN 3 ELSE 4 END,
                   last_confirmed_at DESC
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# Filings (with cursor pagination)
# ---------------------------------------------------------------------------


def _encode_cursor(date_filed: Any, filing_id: str) -> str:
    payload = json.dumps({"d": str(date_filed) if date_filed else None, "i": filing_id})
    return base64.urlsafe_b64encode(payload.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[str | None, str | None]:
    try:
        payload = json.loads(base64.urlsafe_b64decode(cursor.encode()))
        return payload.get("d"), payload.get("i")
    except Exception:
        return None, None


async def get_filings(
    session: AsyncSession,
    company_id: uuid.UUID,
    cursor: str | None = None,
    limit: int = 20,
    category: str | None = None,
) -> tuple[list[dict[str, Any]], str | None]:
    """
    Return filings for a company with cursor pagination (newest first).

    Returns (items, next_cursor).  next_cursor is None when no more pages.
    """
    params: dict[str, Any] = {"cid": str(company_id), "limit": limit + 1}
    filters: list[str] = ["f.company_id = :cid"]

    if category:
        filters.append("f.category = :category")
        params["category"] = category

    cursor_date, cursor_id = _decode_cursor(cursor) if cursor else (None, None)
    if cursor_date and cursor_id:
        filters.append(
            "(f.date_filed, f.id::text) < (:cursor_date, :cursor_id)"
        )
        params["cursor_date"] = cursor_date
        params["cursor_id"] = cursor_id

    where_clause = " AND ".join(filters)

    result = await session.execute(
        sa.text(
            f"""
            SELECT f.id, f.transaction_id, f.category, f.type,
                   f.description, f.action_date, f.date_filed, f.pages,
                   f.paper_filed, f.source_links,
                   EXISTS(
                       SELECT 1 FROM filing_documents fd
                       WHERE fd.filing_id = f.id
                   ) AS has_document,
                   (
                       SELECT fd2.parse_status
                       FROM   filing_documents fd2
                       WHERE  fd2.filing_id = f.id
                       ORDER  BY fd2.updated_at DESC
                       LIMIT  1
                   ) AS parse_status
            FROM   filings f
            WHERE  {where_clause}
            ORDER  BY f.date_filed DESC NULLS LAST, f.id DESC
            LIMIT  :limit
            """
        ),
        params,
    )
    rows = [dict(r) for r in result.mappings()]

    next_cursor = None
    if len(rows) > limit:
        rows = rows[:limit]
        last = rows[-1]
        next_cursor = _encode_cursor(last.get("date_filed"), str(last["id"]))

    return rows, next_cursor


# ---------------------------------------------------------------------------
# Officers
# ---------------------------------------------------------------------------


async def get_officers(
    session: AsyncSession,
    company_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return officer appointments for a company.

    status: "active" (resigned_on IS NULL) | "resigned" | "all" (default).
    """
    params: dict[str, Any] = {"cid": str(company_id)}
    status_clause = ""
    if status == "active":
        status_clause = "AND oa.resigned_on IS NULL"
    elif status == "resigned":
        status_clause = "AND oa.resigned_on IS NOT NULL"

    result = await session.execute(
        sa.text(
            f"""
            SELECT o.name, oa.role, o.nationality, o.occupation,
                   o.country_of_residence,
                   oa.appointed_on, oa.resigned_on,
                   (oa.resigned_on IS NULL) AS is_current,
                   o.date_of_birth_month, o.date_of_birth_year
            FROM   officer_appointments oa
            JOIN   officers o ON o.id = oa.officer_id
            WHERE  oa.company_id = :cid
                   {status_clause}
            ORDER  BY oa.resigned_on NULLS FIRST, oa.appointed_on DESC
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# PSC records
# ---------------------------------------------------------------------------


async def get_psc_records(
    session: AsyncSession,
    company_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return PSC records for a company.

    status: "active" (ceased_on IS NULL) | "ceased" | "all" (default).
    """
    params: dict[str, Any] = {"cid": str(company_id)}
    status_clause = ""
    if status == "active":
        status_clause = "AND ceased_on IS NULL"
    elif status == "ceased":
        status_clause = "AND ceased_on IS NOT NULL"

    result = await session.execute(
        sa.text(
            f"""
            SELECT name, kind, natures_of_control, notified_on, ceased_on,
                   nationality, country_of_residence,
                   (ceased_on IS NULL) AS is_current,
                   date_of_birth_month, date_of_birth_year
            FROM   psc_records
            WHERE  company_id = :cid
                   {status_clause}
            ORDER  BY ceased_on NULLS FIRST, notified_on DESC
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# Charges
# ---------------------------------------------------------------------------


async def get_charges(
    session: AsyncSession,
    company_id: uuid.UUID,
    status: str | None = None,
) -> list[dict[str, Any]]:
    """
    Return charges for a company.

    status: "outstanding" | "satisfied" | "all" (default).
    """
    params: dict[str, Any] = {"cid": str(company_id)}
    status_clause = ""
    if status and status != "all":
        status_clause = "AND status = :status"
        params["status"] = status

    result = await session.execute(
        sa.text(
            f"""
            SELECT charge_id, status, delivered_on, created_on,
                   resolved_on, persons_entitled, particulars,
                   source_last_checked_at
            FROM   charges
            WHERE  company_id = :cid
                   {status_clause}
            ORDER  BY delivered_on DESC NULLS LAST, charge_id
            """
        ),
        params,
    )
    return [dict(r) for r in result.mappings()]


# ---------------------------------------------------------------------------
# Address snippet utility
# ---------------------------------------------------------------------------


def address_snippet(address: dict | None) -> str | None:
    """
    Produce a short display string from a registered_office_address dict.

    Returns the locality (town) or postal_code if available, or None.
    """
    if not address:
        return None
    parts = []
    if locality := address.get("locality"):
        parts.append(locality)
    elif region := address.get("region"):
        parts.append(region)
    if postal_code := address.get("postal_code"):
        parts.append(postal_code)
    return ", ".join(parts) if parts else None
