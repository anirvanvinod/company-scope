"""
Deterministic template fallback for the Phase 6B analysis layer.

Entry point:
    generate_template_summary(ctx: AnalysisContext) -> AISummaryOutput

Used when:
- ai_enabled=false in config
- The AI call times out or returns invalid JSON
- The AI response fails schema validation

The template produces a structured AISummaryOutput that always renders
meaningful content for the company intelligence page. All statements are
traceable to specific fields in the AnalysisContext.

source is always "template" — never "ai".
"""

from __future__ import annotations

from decimal import Decimal

from app.analytics.ai_models import (
    AISummaryOutput,
    AnalysisContext,
    KeyObservation,
    NarrativeParagraph,
)

_STANDARD_CAVEAT = (
    "This summary is based on public filing data extracted from Companies House "
    "records. It is informational only and does not constitute investment, credit, "
    "legal, or accounting advice. Data may be incomplete, delayed, or subject to "
    "restatement."
)


def _fmt_gbp(value: Decimal | None) -> str:
    """Format a GBP value concisely. Returns 'not available' for None."""
    if value is None:
        return "not available"
    abs_val = abs(value)
    sign = "-" if value < 0 else ""
    if abs_val >= 1_000_000:
        return f"{sign}£{abs_val / 1_000_000:.1f}m"
    if abs_val >= 1_000:
        return f"{sign}£{abs_val / 1_000:.0f}k"
    return f"{sign}£{abs_val:.0f}"


def _fmt_pct(value: Decimal | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.1f}%"


def _fmt_ratio(value: Decimal | None) -> str:
    if value is None:
        return "not available"
    return f"{value:.2f}x"


def generate_template_summary(ctx: AnalysisContext) -> AISummaryOutput:
    """
    Build a deterministic AISummaryOutput from the AnalysisContext.

    Does not call any external service. Always succeeds.
    """
    company = ctx.company
    period = ctx.primary_period
    facts = ctx.facts
    metrics = ctx.derived_metrics
    dq = ctx.data_quality

    # --- summary_short ---
    revenue = facts.get("revenue")
    net_profit = facts.get("profit_loss_after_tax")
    period_desc = f"period ending {period.period_end}"

    revenue_str = _fmt_gbp(revenue.value if revenue else None)
    net_profit_str = _fmt_gbp(net_profit.value if net_profit else None)

    summary_short = (
        f"{company.company_name} ({company.company_number}): "
        f"for the {period_desc}, revenue was {revenue_str} "
        f"and net profit/loss after tax was {net_profit_str}. "
        f"Data confidence: {period.confidence_band}."
    )[:280]

    # --- narrative paragraphs ---
    paragraphs: list[NarrativeParagraph] = []

    # Financial overview
    gross_profit = facts.get("gross_profit")
    gpm = metrics.get("gross_profit_margin")
    npm = metrics.get("net_profit_margin")

    overview_parts = [
        f"For the {period_desc}, {company.company_name} reported "
        f"revenue of {revenue_str}."
    ]
    if gross_profit and gross_profit.value is not None:
        overview_parts.append(
            f"Gross profit was {_fmt_gbp(gross_profit.value)}"
            + (f" (gross margin {_fmt_pct(gpm.value)})" if gpm and gpm.value is not None else "")
            + "."
        )
    if net_profit and net_profit.value is not None:
        overview_parts.append(
            f"Net profit/loss after tax was {net_profit_str}"
            + (f" (net margin {_fmt_pct(npm.value)})" if npm and npm.value is not None else "")
            + "."
        )
    paragraphs.append(
        NarrativeParagraph(
            topic="financial_overview",
            text=" ".join(overview_parts),
            confidence_note=(
                f"Overall extraction confidence: {period.confidence_band}."
                if period.confidence_band in ("low", "unavailable")
                else None
            ),
        )
    )

    # Liquidity
    current_assets = facts.get("current_assets")
    creditors_within = facts.get("creditors_due_within_one_year")
    current_ratio = metrics.get("current_ratio")
    cash = facts.get("cash_bank_on_hand")

    if current_assets or cash or current_ratio:
        liq_parts: list[str] = []
        if current_assets and current_assets.value is not None:
            liq_parts.append(
                f"Current assets stood at {_fmt_gbp(current_assets.value)}."
            )
        if creditors_within and creditors_within.value is not None:
            liq_parts.append(
                f"Creditors due within one year were {_fmt_gbp(creditors_within.value)}."
            )
        if current_ratio and current_ratio.value is not None:
            liq_parts.append(f"The current ratio was {_fmt_ratio(current_ratio.value)}.")
        if cash and cash.value is not None:
            liq_parts.append(f"Cash and bank on hand was {_fmt_gbp(cash.value)}.")
        if liq_parts:
            paragraphs.append(
                NarrativeParagraph(topic="liquidity", text=" ".join(liq_parts))
            )

    # Leverage
    leverage = metrics.get("leverage")
    creditors_after = facts.get("creditors_due_after_one_year")
    net_assets = facts.get("net_assets_liabilities")

    if leverage or creditors_after or net_assets:
        lev_parts: list[str] = []
        if net_assets and net_assets.value is not None:
            lev_parts.append(
                f"Net assets/liabilities were {_fmt_gbp(net_assets.value)}."
            )
        if creditors_after and creditors_after.value is not None:
            lev_parts.append(
                f"Long-term creditors (due after one year) were "
                f"{_fmt_gbp(creditors_after.value)}."
            )
        if leverage and leverage.value is not None:
            lev_parts.append(f"Leverage ratio (debt/equity) was {_fmt_ratio(leverage.value)}.")
        if lev_parts:
            paragraphs.append(
                NarrativeParagraph(topic="leverage", text=" ".join(lev_parts))
            )

    # Growth (only if prior period available)
    rev_growth = metrics.get("revenue_growth")
    na_growth = metrics.get("net_assets_growth")

    if dq.has_prior_period and (rev_growth or na_growth):
        growth_parts: list[str] = []
        if rev_growth and rev_growth.value is not None:
            growth_parts.append(f"Revenue growth vs prior period was {_fmt_pct(rev_growth.value)}.")
        if na_growth and na_growth.value is not None:
            growth_parts.append(
                f"Net assets growth vs prior period was {_fmt_pct(na_growth.value)}."
            )
        if growth_parts:
            paragraphs.append(
                NarrativeParagraph(topic="growth", text=" ".join(growth_parts))
            )

    # Data quality note (separate paragraph)
    dq_issues: list[str] = []
    if dq.facts_available_count < 6:
        dq_issues.append(
            f"Only {dq.facts_available_count} of {dq.facts_total} expected "
            f"financial facts were available in this filing."
        )
    if dq.warnings:
        dq_issues.extend(dq.warnings)
    if dq_issues:
        paragraphs.append(
            NarrativeParagraph(
                topic="data_quality",
                text=" ".join(dq_issues),
            )
        )

    # --- key observations from fired signals ---
    observations: list[KeyObservation] = []
    for signal in ctx.signals:
        if signal.fired:
            observations.append(
                KeyObservation(
                    observation=signal.evidence_summary,
                    severity=signal.severity,
                    evidence_ref=signal.signal_key,
                )
            )
    # Cap at 5 per spec
    observations = observations[:5]

    # --- data_quality_note ---
    dq_note: str | None = None
    if dq.facts_available_count < 6 or dq.warnings:
        parts = []
        if dq.facts_available_count < 6:
            parts.append(
                f"{dq.facts_available_count}/{dq.facts_total} expected facts available"
            )
        if dq.primary_period_confidence_band in ("low", "unavailable"):
            parts.append(
                f"extraction confidence is {dq.primary_period_confidence_band}"
            )
        if parts:
            dq_note = "Data quality note: " + "; ".join(parts) + "."

    # --- caveats ---
    caveats = [_STANDARD_CAVEAT]
    if period.accounts_type in ("micro-entity", "dormant"):
        caveats.append(
            f"These accounts were filed as {period.accounts_type} accounts. "
            "Financial detail is limited by statutory abridgement rules."
        )

    return AISummaryOutput(
        summary_short=summary_short,
        narrative_paragraphs=paragraphs,
        key_observations=observations,
        data_quality_note=dq_note,
        caveats=caveats,
        source="template",
    )
