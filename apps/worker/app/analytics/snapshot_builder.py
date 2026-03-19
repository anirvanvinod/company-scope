"""
Snapshot builder for the Phase 6B analysis layer.

Entry point:
    build_company_snapshot(company_number, session) -> CompanySnapshotPayload

Assembles the full company read-model by:
1. Resolving primary and prior financial periods.
2. Building the AnalysisContext (all structured inputs).
3. Attempting AI narrative generation (if ai_enabled=true).
4. Falling back to the deterministic template if AI fails or is disabled.
5. Returning a CompanySnapshotPayload ready for JSONB persistence.

Internal accessor (Phase 7 interface):
    get_snapshot_for_company(company_id, session) -> dict | None
        Returns the current snapshot payload dict, or None if not yet built.

These functions do not commit to the DB. The caller (snapshot Celery task)
is responsible for upsert and commit.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

import sqlalchemy as sa

from app.analytics.ai_client import AICallFailed, generate_ai_summary
from app.analytics.ai_models import AnalysisContext, CompanySnapshotPayload
from app.analytics.context_builder import build_analysis_context
from app.analytics.fallback import generate_template_summary
from app.analytics.metrics import METHODOLOGY_VERSION
from app.analytics.period_selector import (
    get_primary_period_for_analysis,
    get_prior_period_for_analysis,
)
from app.config import settings

log = logging.getLogger(__name__)


def _build_financial_summary(ctx: AnalysisContext) -> dict:
    """Extract key financial figures from the analysis context for the snapshot."""
    def fact_val(key: str):
        fv = ctx.facts.get(key)
        if fv and fv.value is not None:
            return float(fv.value)
        return None

    return {
        "latest_period_end": ctx.primary_period.period_end,
        "period_start": ctx.primary_period.period_start,
        "accounts_type": ctx.primary_period.accounts_type,
        "currency_code": ctx.primary_period.currency_code,
        "confidence": float(ctx.primary_period.extraction_confidence),
        "confidence_band": ctx.primary_period.confidence_band,
        "revenue": fact_val("revenue"),
        "net_assets_liabilities": fact_val("net_assets_liabilities"),
        "profit_loss_after_tax": fact_val("profit_loss_after_tax"),
        "average_number_of_employees": fact_val("average_number_of_employees"),
    }


async def _fetch_active_signals(
    session: AsyncSession, company_id: uuid.UUID
) -> list[dict]:
    """Fetch currently active risk signals for the snapshot payload."""
    result = await session.execute(
        sa.text(
            """
            SELECT signal_code, signal_name, category, severity, explanation
            FROM   risk_signals
            WHERE  company_id = :cid
              AND  status     = 'active'
            ORDER  BY severity DESC, signal_code
            """
        ),
        {"cid": str(company_id)},
    )
    return [dict(row._mapping) for row in result.fetchall()]


async def build_company_snapshot(
    company_number: str,
    session: AsyncSession,
) -> tuple[uuid.UUID, CompanySnapshotPayload]:
    """
    Build a full CompanySnapshotPayload for the given company.

    Returns (company_id, payload).

    Raises ValueError if the company is not in the DB or has no primary period.
    Does not persist — call upsert_company_snapshot() with the result.
    """
    # --- resolve company_id ---
    result = await session.execute(
        sa.text("SELECT id FROM companies WHERE company_number = :cn"),
        {"cn": company_number},
    )
    company_id: uuid.UUID | None = result.scalar_one_or_none()
    if company_id is None:
        raise ValueError(
            f"Company {company_number!r} not found. Run refresh_company first."
        )

    # --- resolve primary and prior periods ---
    primary = await get_primary_period_for_analysis(session, company_id)
    if primary is None:
        raise ValueError(
            f"No qualifying financial period for {company_number!r}. "
            "Run extract_facts and compute_analysis first."
        )
    prior = await get_prior_period_for_analysis(session, company_id, primary)

    # --- build analysis context ---
    ctx = await build_analysis_context(session, company_id, primary, prior)

    # --- AI narrative (or fallback) ---
    summary_source = "template"
    if settings.ai_enabled:
        try:
            ai_output = await generate_ai_summary(ctx, company_id, primary.period_id)
            summary_source = "ai"
        except AICallFailed as exc:
            log.warning(
                "AI summary failed for %s, falling back to template: %s",
                company_number,
                exc,
            )
            ai_output = generate_template_summary(ctx)
    else:
        ai_output = generate_template_summary(ctx)

    financial_summary = _build_financial_summary(ctx)
    active_signals = await _fetch_active_signals(session, company_id)

    payload = CompanySnapshotPayload(
        company_number=company_number,
        analysis_context=ctx.model_dump(mode="json"),
        ai_summary=ai_output.model_dump(mode="json"),
        summary_source=summary_source,
        methodology_version=METHODOLOGY_VERSION,
        model_version=settings.ai_model_name if summary_source == "ai" else "",
        financial_summary=financial_summary,
        active_signals=active_signals,
    )

    log.info(
        "Snapshot built for %s: period_end=%s source=%s",
        company_number,
        primary.period_end,
        summary_source,
    )
    return company_id, payload


async def get_snapshot_for_company(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> dict[str, Any] | None:
    """
    Return the current snapshot payload for a company, or None if not found.

    Phase 7 interface: the API service calls this to render the company page.
    Returns the raw dict from the JSONB column (already deserialized by asyncpg).
    """
    result = await session.execute(
        sa.text(
            """
            SELECT snapshot_payload
            FROM   company_snapshots
            WHERE  company_id = :cid
              AND  is_current  = true
            LIMIT  1
            """
        ),
        {"cid": str(company_id)},
    )
    row = result.one_or_none()
    if row is None:
        return None
    return row[0]  # asyncpg returns JSONB as a Python dict
