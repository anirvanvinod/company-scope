"""
Context builder for the Phase 6B analysis layer.

Entry point:
    build_analysis_context(session, company_id, primary, prior) -> AnalysisContext

Assembles the AnalysisContext that is passed to the AI model or template
fallback.  All data comes from the DB; no external calls are made here.

Canonical facts included in the AI context (per docs/10-ai-analysis-layer-spec.md):
    revenue, gross_profit, operating_profit_loss, profit_loss_after_tax,
    current_assets, fixed_assets, total_assets_less_current_liabilities,
    creditors_due_within_one_year, creditors_due_after_one_year,
    net_assets_liabilities, cash_bank_on_hand, average_number_of_employees

Derived metrics included:
    gross_profit_margin, operating_profit_margin, net_profit_margin,
    current_ratio, leverage, revenue_growth, net_assets_growth
"""

from __future__ import annotations

import uuid
from decimal import Decimal

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from app.analytics.ai_models import (
    AnalysisContext,
    CompanyInfo,
    DataQualityInfo,
    FactValue,
    PrimaryPeriodInfo,
    SignalInfo,
)
from app.analytics.models import PeriodSnapshot
from app.analytics.period_selector import get_facts_for_period
from app.parsers.confidence import confidence_band

# Canonical fact names included in the AI context (12 total per spec).
_CONTEXT_FACTS = [
    "revenue",
    "gross_profit",
    "operating_profit_loss",
    "profit_loss_after_tax",
    "current_assets",
    "fixed_assets",
    "total_assets_less_current_liabilities",
    "creditors_due_within_one_year",
    "creditors_due_after_one_year",
    "net_assets_liabilities",
    "cash_bank_on_hand",
    "average_number_of_employees",
]

# Metric keys included in the AI context (7 total per spec).
_CONTEXT_METRICS = [
    "gross_profit_margin",
    "operating_profit_margin",
    "net_profit_margin",
    "current_ratio",
    "leverage",
    "revenue_growth",
    "net_assets_growth",
]


async def _fetch_company_row(
    session: AsyncSession, company_id: uuid.UUID
) -> dict:
    """Fetch all company fields needed for AI context from DB."""
    result = await session.execute(
        sa.text(
            """
            SELECT company_number, company_name, company_status, company_type,
                   date_of_creation, sic_codes, accounts_overdue
            FROM   companies
            WHERE  id = :cid
            """
        ),
        {"cid": str(company_id)},
    )
    row = result.mappings().one_or_none()
    if row is None:
        return {}
    return dict(row)


async def _fetch_derived_metrics(
    session: AsyncSession,
    company_id: uuid.UUID,
    financial_period_id: uuid.UUID,
) -> dict[str, FactValue]:
    """
    Fetch derived metrics for the primary period from the DB.

    Returns a dict mapping metric_key → FactValue.
    Only the metrics listed in _CONTEXT_METRICS are included.
    """
    keys_placeholder = ", ".join(f"'{k}'" for k in _CONTEXT_METRICS)
    result = await session.execute(
        sa.text(
            f"""
            SELECT metric_key, metric_value, confidence, confidence_band
            FROM   derived_metrics
            WHERE  company_id          = :cid
              AND  financial_period_id = :pid
              AND  metric_key          IN ({keys_placeholder})
            """
        ),
        {"cid": str(company_id), "pid": str(financial_period_id)},
    )
    out: dict[str, FactValue] = {}
    for row in result.mappings():
        out[row["metric_key"]] = FactValue(
            value=Decimal(str(row["metric_value"])) if row["metric_value"] is not None else None,
            confidence=Decimal(str(row["confidence"])) if row["confidence"] is not None else Decimal("0"),
            band=row["confidence_band"] or "unavailable",
        )
    return out


async def _fetch_signals(
    session: AsyncSession,
    company_id: uuid.UUID,
) -> list[SignalInfo]:
    """
    Fetch current risk signals for a company.

    Returns only signals evaluated on the latest methodology pass (status !=
    'superseded').  Both fired and non-fired signals are included so the AI can
    note absences of expected risks.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT signal_code, severity, status, explanation, evidence
            FROM   risk_signals
            WHERE  company_id = :cid
              AND  status     != 'superseded'
            ORDER  BY severity DESC, signal_code
            """
        ),
        {"cid": str(company_id)},
    )
    out: list[SignalInfo] = []
    for row in result.mappings():
        fired = row["status"] == "active"
        # Use first sentence of explanation as evidence_summary for AI context
        explanation = row["explanation"] or ""
        evidence_summary = explanation.split(".")[0].strip()
        out.append(
            SignalInfo(
                signal_key=row["signal_code"],
                severity=row["severity"],
                fired=fired,
                evidence_summary=evidence_summary,
            )
        )
    return out


async def build_analysis_context(
    session: AsyncSession,
    company_id: uuid.UUID,
    primary: PeriodSnapshot,
    prior: PeriodSnapshot | None,
) -> AnalysisContext:
    """
    Assemble an AnalysisContext from DB data.

    Reads: companies, financial_facts, derived_metrics, risk_signals.
    Does not make external calls.
    """
    # Company info
    company_row = await _fetch_company_row(session, company_id)
    company_info = CompanyInfo(
        company_number=company_row.get("company_number", ""),
        company_name=company_row.get("company_name", ""),
        company_status=company_row.get("company_status"),
        company_type=company_row.get("company_type"),
        sic_codes=list(company_row.get("sic_codes") or []),
        date_of_creation=(
            company_row["date_of_creation"].isoformat()
            if company_row.get("date_of_creation")
            else None
        ),
        accounts_overdue=bool(company_row.get("accounts_overdue") or False),
    )

    # Primary period info
    band = confidence_band(primary.extraction_confidence)
    primary_info = PrimaryPeriodInfo(
        period_end=primary.period_end.isoformat(),
        period_start=primary.period_start.isoformat() if primary.period_start else None,
        accounts_type=primary.accounts_type,
        currency_code="GBP",
        extraction_confidence=primary.extraction_confidence,
        confidence_band=band,
    )

    # Raw facts for primary period
    raw_facts = await get_facts_for_period(session, primary.period_id)
    facts: dict[str, FactValue] = {}
    for key in _CONTEXT_FACTS:
        snap = raw_facts.get(key)
        if snap is not None:
            facts[key] = FactValue(
                value=snap.value,
                confidence=snap.confidence,
                band=confidence_band(snap.confidence),
            )
        else:
            facts[key] = FactValue(value=None, confidence=Decimal("0"), band="unavailable")

    # Derived metrics
    derived = await _fetch_derived_metrics(session, company_id, primary.period_id)
    for key in _CONTEXT_METRICS:
        if key not in derived:
            derived[key] = FactValue(value=None, confidence=Decimal("0"), band="unavailable")

    # Signals
    signals = await _fetch_signals(session, company_id)

    # Data quality
    available_count = sum(1 for f in facts.values() if f.value is not None)
    dq_warnings: list[str] = []
    if primary.extraction_confidence < Decimal("0.65"):
        dq_warnings.append(
            f"Primary period extraction confidence is {band} "
            f"({float(primary.extraction_confidence):.0%})."
        )

    data_quality = DataQualityInfo(
        facts_available_count=available_count,
        facts_total=len(_CONTEXT_FACTS),
        primary_period_confidence_band=band,
        has_prior_period=prior is not None,
        warnings=dq_warnings,
    )

    return AnalysisContext(
        company=company_info,
        primary_period=primary_info,
        facts=facts,
        derived_metrics=derived,
        signals=signals,
        data_quality=data_quality,
    )
