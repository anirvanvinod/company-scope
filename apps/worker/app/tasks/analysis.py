"""
Financial analysis Celery task — Phase 6A.

compute_analysis(company_number)
    Resolves the primary and prior financial periods for a company, computes
    all derived metrics (M1–M9) and rule-based signals (S1–S13), and persists
    the results to derived_metrics and risk_signals.

    Triggered automatically after extract_facts completes with at least one
    successfully extracted document.  May also be called independently to
    recompute analysis after methodology version changes.

Idempotency:
    All writes are ON CONFLICT DO UPDATE (derived_metrics, risk_signals).
    Re-running the task overwrites with the most recent computation.
    If no primary period is found, the task logs and returns early.

Non-retryable: ValueError (company not in DB).
Retryable: transient DB errors, unexpected exceptions.
"""

from __future__ import annotations

import asyncio
import logging
import uuid
from typing import Any

import sqlalchemy as sa

from app.analytics.metrics import METHODOLOGY_VERSION, compute_all_metrics
from app.analytics.models import PeriodSnapshot
from app.analytics.period_selector import (
    get_company_profile_for_analysis,
    get_facts_for_period,
    get_primary_period_for_analysis,
    get_prior_period_for_analysis,
)
from app.analytics.signals import compute_all_signals
from app.db import get_session
from app.main import celery_app
from app.repositories import upsert_derived_metrics, upsert_risk_signals

log = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Async implementation
# ---------------------------------------------------------------------------


async def _compute_analysis_async(company_number: str) -> dict[str, Any]:
    # --- resolve company_id ---
    async with get_session() as session:
        result = await session.execute(
            sa.text("SELECT id FROM companies WHERE company_number = :cn"),
            {"cn": company_number},
        )
        company_id: uuid.UUID | None = result.scalar_one_or_none()

    if company_id is None:
        raise ValueError(
            f"Company {company_number!r} not found in DB. "
            "Run refresh_company first."
        )

    # --- resolve primary period ---
    async with get_session() as session:
        primary = await get_primary_period_for_analysis(session, company_id)

    if primary is None:
        log.info(
            "No qualifying financial period for analysis for %s — skipping",
            company_number,
        )
        return {
            "company_number": company_number,
            "status": "no_primary_period",
            "metrics_computed": 0,
            "signals_evaluated": 0,
        }

    # --- resolve prior period ---
    async with get_session() as session:
        prior = await get_prior_period_for_analysis(session, company_id, primary)

    # --- fetch facts ---
    async with get_session() as session:
        primary_facts = await get_facts_for_period(session, primary.period_id)

    prior_facts: dict | None = None
    if prior is not None:
        async with get_session() as session:
            prior_facts = await get_facts_for_period(session, prior.period_id)

    # --- fetch company profile ---
    async with get_session() as session:
        profile = await get_company_profile_for_analysis(session, company_id)

    # --- compute metrics ---
    metric_results = compute_all_metrics(
        primary_facts=primary_facts,
        prior_facts=prior_facts,
        primary_period=primary,
        prior_period=prior,
    )
    metrics_map = {r.metric_key: r for r in metric_results}

    # --- compute signals ---
    signal_results = compute_all_signals(
        primary_facts=primary_facts,
        prior_facts=prior_facts,
        metrics=metrics_map,
        company_profile=profile,
        primary_period=primary,
        prior_period=prior,
    )

    # --- persist ---
    prior_period_id: uuid.UUID | None = prior.period_id if prior is not None else None

    async with get_session() as session:
        await upsert_derived_metrics(
            session,
            company_id=company_id,
            financial_period_id=primary.period_id,
            prior_period_id=prior_period_id,
            results=metric_results,
            methodology_version=METHODOLOGY_VERSION,
        )
        await upsert_risk_signals(
            session,
            company_id=company_id,
            results=signal_results,
            methodology_version=METHODOLOGY_VERSION,
        )
        await session.commit()

    fired_count = sum(1 for s in signal_results if s.fired)
    log.info(
        "Analysis complete for %s: %d metrics, %d signals (%d fired), "
        "period=%s, prior=%s",
        company_number,
        len(metric_results),
        len(signal_results),
        fired_count,
        primary.period_end,
        prior.period_end if prior else None,
    )

    # Enqueue snapshot build now that analysis results are persisted.
    from app.tasks.snapshot import build_snapshot  # local import avoids circular
    build_snapshot.apply_async(args=[company_number])

    return {
        "company_number": company_number,
        "status": "ok",
        "primary_period_end": str(primary.period_end),
        "prior_period_end": str(prior.period_end) if prior else None,
        "metrics_computed": len(metric_results),
        "signals_evaluated": len(signal_results),
        "signals_fired": fired_count,
    }


# ---------------------------------------------------------------------------
# Celery task definition
# ---------------------------------------------------------------------------


@celery_app.task(
    bind=True,
    name="analysis.compute_analysis",
    queue="document_parse",
    max_retries=3,
    default_retry_delay=60,
)
def compute_analysis(self: Any, company_number: str) -> dict[str, Any]:
    """
    Compute derived metrics and rule-based signals for a company.

    Enqueue after extract_facts completes.  Safe to re-run at any time.

    Non-retryable: ValueError (company not in DB).
    Retryable: transient DB errors.
    """
    try:
        return asyncio.run(_compute_analysis_async(company_number))
    except ValueError:
        raise  # non-retryable
    except Exception as exc:
        log.exception("compute_analysis failed for %s: %s", company_number, exc)
        raise self.retry(exc=exc)
