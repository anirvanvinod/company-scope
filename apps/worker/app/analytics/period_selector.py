"""
Period selection logic for the Phase 6A analysis layer.

Provides async functions that query the DB to resolve:
  - the primary period (most recent with adequate confidence)
  - the prior period (most recent before primary, within 18-month gap)
  - facts for a period
  - company profile fields needed by signals

All queries use raw SQL via sa.text() consistent with the rest of the worker.
"""

from __future__ import annotations

import uuid
from datetime import timedelta
from decimal import Decimal
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.models import CompanyProfile, FactSnapshot, PeriodSnapshot

# Minimum extraction confidence to use a period for analysis
MIN_PERIOD_CONFIDENCE = Decimal("0.40")

# Maximum gap between primary period_start and prior period_end.
# 18 months ≈ 548 days; growth metrics are suppressed beyond this gap.
MAX_PRIOR_GAP_DAYS = 548


async def get_primary_period_for_analysis(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> PeriodSnapshot | None:
    """
    Return the most recent non-restated financial period for a company
    whose extraction_confidence >= MIN_PERIOD_CONFIDENCE.

    Returns None if no qualifying period exists.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT id, period_end, period_start, extraction_confidence, accounts_type
            FROM   financial_periods
            WHERE  company_id          = :cid
              AND  extraction_confidence >= :min_conf
              AND  is_restated           = false
            ORDER  BY period_end DESC
            LIMIT  1
            """
        ),
        {"cid": str(company_id), "min_conf": float(MIN_PERIOD_CONFIDENCE)},
    )
    row = result.one_or_none()
    if row is None:
        return None
    return PeriodSnapshot(
        period_id=row.id,
        period_end=row.period_end,
        period_start=row.period_start,
        extraction_confidence=Decimal(str(row.extraction_confidence)),
        accounts_type=row.accounts_type,
    )


async def get_prior_period_for_analysis(
    session: AsyncSession,
    company_id: uuid.UUID,
    primary: PeriodSnapshot,
) -> PeriodSnapshot | None:
    """
    Return the most recent non-restated period before primary.period_end
    that falls within MAX_PRIOR_GAP_DAYS of primary.period_start (or
    primary.period_end if period_start is unknown).

    Returns None if no qualifying prior period exists.
    """
    reference_date = primary.period_start or primary.period_end
    cutoff = reference_date - timedelta(days=MAX_PRIOR_GAP_DAYS)

    result = await session.execute(
        sa.text(
            """
            SELECT id, period_end, period_start, extraction_confidence, accounts_type
            FROM   financial_periods
            WHERE  company_id          = :cid
              AND  period_end          < :primary_end
              AND  period_end          >= :cutoff
              AND  extraction_confidence >= :min_conf
              AND  is_restated           = false
            ORDER  BY period_end DESC
            LIMIT  1
            """
        ),
        {
            "cid": str(company_id),
            "primary_end": primary.period_end,
            "cutoff": cutoff,
            "min_conf": float(MIN_PERIOD_CONFIDENCE),
        },
    )
    row = result.one_or_none()
    if row is None:
        return None
    return PeriodSnapshot(
        period_id=row.id,
        period_end=row.period_end,
        period_start=row.period_start,
        extraction_confidence=Decimal(str(row.extraction_confidence)),
        accounts_type=row.accounts_type,
    )


async def get_facts_for_period(
    session: AsyncSession,
    period_id: uuid.UUID,
) -> dict[str, FactSnapshot]:
    """
    Return all financial facts for a period as a dict keyed by fact_name.

    Facts with null fact_value are included with value=None (caller must
    not default these to zero).
    Facts with null extraction_confidence are assigned confidence=0 so
    downstream guards treat them as below the minimum threshold.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT fact_name, fact_value, extraction_confidence
            FROM   financial_facts
            WHERE  financial_period_id = :pid
            """
        ),
        {"pid": str(period_id)},
    )
    facts: dict[str, FactSnapshot] = {}
    for row in result.fetchall():
        conf = Decimal(str(row.extraction_confidence)) if row.extraction_confidence is not None else Decimal("0")
        value = Decimal(str(row.fact_value)) if row.fact_value is not None else None
        facts[row.fact_name] = FactSnapshot(value=value, confidence=conf)
    return facts


async def get_company_profile_for_analysis(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> CompanyProfile:
    """
    Return the company profile fields needed by signal evaluation.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT accounts_overdue, company_status
            FROM   companies
            WHERE  id = :cid
            """
        ),
        {"cid": str(company_id)},
    )
    row = result.one_or_none()
    if row is None:
        return CompanyProfile(accounts_overdue=None, company_status=None)
    return CompanyProfile(
        accounts_overdue=row.accounts_overdue,
        company_status=row.company_status,
    )
