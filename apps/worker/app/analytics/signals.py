"""
Deterministic rule-based financial signal computation — Phase 6A.

Implements S1–S13 from docs/09-financial-analysis-spec.md.

All functions are pure: no DB access, no advisory language.
Each signal function returns SignalResult | None.
  - SignalResult(fired=True)  → signal is currently active
  - SignalResult(fired=False) → signal was evaluated, condition not met
  - None                      → insufficient data to evaluate; DB row untouched

Entry point:
    compute_all_signals(
        primary_facts, prior_facts, metrics, company_profile,
        primary_period, prior_period
    ) -> list[SignalResult]

Only non-None results are returned.  Callers upsert each result.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from app.analytics.models import (
    CompanyProfile,
    FactSnapshot,
    MetricResult,
    PeriodSnapshot,
    SignalResult,
)

METHODOLOGY_VERSION = "1.0.0"

# Canonical fact names checked for S13 coverage count.
_ALL_CANONICAL = frozenset({
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
})

_S13_THRESHOLD = 6      # fire S13 when >= this many facts are missing/low-conf
_MIN_CONF_LOW = Decimal("0.40")
_MIN_CONF_MEDIUM = Decimal("0.65")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _fact_ok_low(f: FactSnapshot | None) -> bool:
    return f is not None and f.value is not None and f.confidence >= _MIN_CONF_LOW


def _fact_ok_medium(f: FactSnapshot | None) -> bool:
    return f is not None and f.value is not None and f.confidence >= _MIN_CONF_MEDIUM


def _metric_val(metrics: dict[str, MetricResult], key: str) -> Decimal | None:
    m = metrics.get(key)
    return m.metric_value if m is not None else None


def _metric_conf(metrics: dict[str, MetricResult], key: str) -> Decimal | None:
    m = metrics.get(key)
    return m.confidence if m is not None else None


def _metric_ok_medium(metrics: dict[str, MetricResult], key: str) -> bool:
    conf = _metric_conf(metrics, key)
    val = _metric_val(metrics, key)
    return conf is not None and conf >= _MIN_CONF_MEDIUM and val is not None


# ---------------------------------------------------------------------------
# S1 — Negative net assets
# ---------------------------------------------------------------------------


def _s1(pf: dict[str, FactSnapshot]) -> SignalResult | None:
    nal = pf.get("net_assets_liabilities")
    if not _fact_ok_low(nal):
        return None
    assert nal is not None and nal.value is not None
    fired = nal.value < 0
    return SignalResult(
        signal_code="negative_net_assets",
        signal_name="Negative net assets",
        category="financial_risk",
        severity="high",
        fired=fired,
        explanation=(
            f"Net assets reported as {nal.value} (confidence: {nal.confidence:.2f})."
            if fired
            else "Net assets are positive."
        ),
        evidence={"net_assets_liabilities": str(nal.value), "confidence": str(nal.confidence)},
    )


# ---------------------------------------------------------------------------
# S2 — Negative net assets, worsening
# ---------------------------------------------------------------------------


def _s2(
    pf: dict[str, FactSnapshot],
    prior_pf: dict[str, FactSnapshot],
) -> SignalResult | None:
    nal_c = pf.get("net_assets_liabilities")
    nal_p = prior_pf.get("net_assets_liabilities")
    if not _fact_ok_medium(nal_c) or not _fact_ok_medium(nal_p):
        return None
    assert nal_c is not None and nal_p is not None
    assert nal_c.value is not None and nal_p.value is not None
    fired = nal_c.value < nal_p.value < 0
    return SignalResult(
        signal_code="negative_net_assets_worsening",
        signal_name="Net assets negative and worsening",
        category="financial_risk",
        severity="high",
        fired=fired,
        explanation=(
            f"Net assets declined from {nal_p.value} to {nal_c.value}."
            if fired
            else "Net assets negative and worsening condition not met."
        ),
        evidence={
            "net_assets_current": str(nal_c.value),
            "net_assets_prior": str(nal_p.value),
        },
    )


# ---------------------------------------------------------------------------
# S3 — Significant revenue decline
# ---------------------------------------------------------------------------


def _s3(metrics: dict[str, MetricResult]) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "revenue_growth"):
        return None
    val = _metric_val(metrics, "revenue_growth")
    assert val is not None
    if val >= Decimal("-0.20"):
        return SignalResult(
            signal_code="significant_revenue_decline",
            signal_name="Significant revenue decline",
            category="financial_risk",
            severity="medium",
            fired=False,
            explanation="Revenue growth within acceptable range.",
            evidence={"revenue_growth": str(val)},
        )
    severity = "high" if val < Decimal("-0.40") else "medium"
    return SignalResult(
        signal_code="significant_revenue_decline",
        signal_name="Significant revenue decline",
        category="financial_risk",
        severity=severity,
        fired=True,
        explanation=f"Revenue declined by {abs(val) * 100:.1f}% year-on-year.",
        evidence={"revenue_growth": str(val)},
    )


# ---------------------------------------------------------------------------
# S4 — Liquidity pressure (current ratio < 1.0)
# ---------------------------------------------------------------------------


def _s4(metrics: dict[str, MetricResult]) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "current_ratio"):
        return None
    val = _metric_val(metrics, "current_ratio")
    assert val is not None
    fired = val < Decimal("1.0")
    return SignalResult(
        signal_code="liquidity_pressure",
        signal_name="Liquidity pressure",
        category="financial_risk",
        severity="medium",
        fired=fired,
        explanation=(
            f"Current ratio is {val:.2f}, below 1.0."
            if fired
            else f"Current ratio is {val:.2f}."
        ),
        evidence={"current_ratio": str(val)},
    )


# ---------------------------------------------------------------------------
# S5 — Severe liquidity pressure (current ratio < 0.5)
# ---------------------------------------------------------------------------


def _s5(metrics: dict[str, MetricResult]) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "current_ratio"):
        return None
    val = _metric_val(metrics, "current_ratio")
    assert val is not None
    fired = val < Decimal("0.5")
    return SignalResult(
        signal_code="severe_liquidity_pressure",
        signal_name="Severe liquidity pressure",
        category="financial_risk",
        severity="high",
        fired=fired,
        explanation=(
            f"Current ratio is {val:.2f}, severely below 1.0."
            if fired
            else f"Current ratio is {val:.2f}."
        ),
        evidence={"current_ratio": str(val)},
    )


# ---------------------------------------------------------------------------
# S6 — Cash concentration risk
# ---------------------------------------------------------------------------


def _s6(metrics: dict[str, MetricResult]) -> SignalResult | None:
    cr_ok = _metric_ok_medium(metrics, "current_ratio")
    cash_ok = _metric_ok_medium(metrics, "cash_ratio")
    if not cr_ok or not cash_ok:
        return None
    cr_val = _metric_val(metrics, "current_ratio")
    cash_val = _metric_val(metrics, "cash_ratio")
    assert cr_val is not None and cash_val is not None
    fired = cash_val < Decimal("0.05") and cr_val < Decimal("1.2")
    return SignalResult(
        signal_code="cash_concentration_risk",
        signal_name="Cash concentration risk",
        category="financial_risk",
        severity="medium",
        fired=fired,
        explanation=(
            f"Cash ratio is {cash_val:.3f} and current ratio is {cr_val:.2f}."
            if fired
            else "Cash position relative to current liabilities is adequate."
        ),
        evidence={"cash_ratio": str(cash_val), "current_ratio": str(cr_val)},
    )


# ---------------------------------------------------------------------------
# S7 — High leverage (> 3.0)
# ---------------------------------------------------------------------------


def _s7(metrics: dict[str, MetricResult]) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "leverage"):
        return None
    val = _metric_val(metrics, "leverage")
    assert val is not None
    fired = val > Decimal("3.0")
    return SignalResult(
        signal_code="high_leverage",
        signal_name="High leverage",
        category="financial_risk",
        severity="medium",
        fired=fired,
        explanation=(
            f"Leverage proxy is {val:.2f}x."
            if fired
            else f"Leverage proxy is {val:.2f}x."
        ),
        evidence={"leverage": str(val)},
    )


# ---------------------------------------------------------------------------
# S8 — Extreme leverage (> 10.0)
# ---------------------------------------------------------------------------


def _s8(metrics: dict[str, MetricResult]) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "leverage"):
        return None
    val = _metric_val(metrics, "leverage")
    assert val is not None
    fired = val > Decimal("10.0")
    return SignalResult(
        signal_code="extreme_leverage",
        signal_name="Extreme leverage",
        category="financial_risk",
        severity="high",
        fired=fired,
        explanation=(
            f"Leverage proxy is {val:.2f}x."
            if fired
            else f"Leverage proxy is {val:.2f}x, below extreme threshold."
        ),
        evidence={"leverage": str(val)},
    )


# ---------------------------------------------------------------------------
# S9 — Accounts overdue
# ---------------------------------------------------------------------------


def _s9(profile: CompanyProfile) -> SignalResult | None:
    if profile.accounts_overdue is None:
        return None
    # Suppress for dissolved companies (accounts overdue is expected there).
    if profile.company_status == "dissolved":
        return None
    fired = profile.accounts_overdue is True
    return SignalResult(
        signal_code="accounts_overdue",
        signal_name="Accounts overdue",
        category="filing_risk",
        severity="high",
        fired=fired,
        explanation=(
            "Companies House records show accounts are overdue."
            if fired
            else "Accounts are not currently overdue."
        ),
        evidence={"accounts_overdue": profile.accounts_overdue},
    )


# ---------------------------------------------------------------------------
# S10 — No recent accounts
# ---------------------------------------------------------------------------


def _s10(primary_period: PeriodSnapshot | None) -> SignalResult:
    """Always evaluated — returns fired or not-fired, never None."""
    cutoff = date.today() - timedelta(days=730)  # 24 months
    if primary_period is None:
        return SignalResult(
            signal_code="no_recent_accounts",
            signal_name="No recent accounts extracted",
            category="filing_risk",
            severity="medium",
            fired=True,
            explanation="No financial period has been successfully extracted for this company.",
            evidence={"primary_period": None},
        )
    fired = primary_period.period_end < cutoff
    return SignalResult(
        signal_code="no_recent_accounts",
        signal_name="No recent accounts extracted",
        category="filing_risk",
        severity="medium",
        fired=fired,
        explanation=(
            f"Most recent accounts period ended {primary_period.period_end}, over 24 months ago."
            if fired
            else f"Most recent accounts period ended {primary_period.period_end}."
        ),
        evidence={"period_end": str(primary_period.period_end)},
    )


# ---------------------------------------------------------------------------
# S11 — Positive revenue momentum
# ---------------------------------------------------------------------------


def _s11(
    pf: dict[str, FactSnapshot],
    metrics: dict[str, MetricResult],
) -> SignalResult | None:
    if not _metric_ok_medium(metrics, "revenue_growth"):
        return None
    val = _metric_val(metrics, "revenue_growth")
    assert val is not None
    ebit = pf.get("operating_profit_loss")
    # Fire when growth > 10% AND (EBIT is positive OR EBIT is unavailable)
    ebit_positive_or_absent = (
        ebit is None
        or ebit.value is None
        or ebit.value >= 0
    )
    fired = val > Decimal("0.10") and ebit_positive_or_absent
    return SignalResult(
        signal_code="positive_revenue_momentum",
        signal_name="Positive revenue momentum",
        category="financial_risk",
        severity="informational",
        fired=fired,
        explanation=(
            f"Revenue grew by {val * 100:.1f}% year-on-year."
            if fired
            else "Revenue growth below positive momentum threshold."
        ),
        evidence={"revenue_growth": str(val)},
    )


# ---------------------------------------------------------------------------
# S12 — Consistent profitability
# ---------------------------------------------------------------------------


def _s12(
    pf: dict[str, FactSnapshot],
    prior_pf: dict[str, FactSnapshot],
) -> SignalResult | None:
    pat_c = pf.get("profit_loss_after_tax")
    pat_p = prior_pf.get("profit_loss_after_tax")
    if not _fact_ok_medium(pat_c) or not _fact_ok_medium(pat_p):
        return None
    assert pat_c is not None and pat_p is not None
    assert pat_c.value is not None and pat_p.value is not None
    fired = pat_c.value > 0 and pat_p.value > 0
    return SignalResult(
        signal_code="consistent_profitability",
        signal_name="Consistent profitability",
        category="financial_risk",
        severity="informational",
        fired=fired,
        explanation=(
            f"Profit after tax was positive in both periods ({pat_p.value} and {pat_c.value})."
            if fired
            else "Profit after tax was not positive in both consecutive periods."
        ),
        evidence={
            "profit_loss_after_tax_current": str(pat_c.value),
            "profit_loss_after_tax_prior": str(pat_p.value),
        },
    )


# ---------------------------------------------------------------------------
# S13 — Data quality warning
# ---------------------------------------------------------------------------


def _s13(pf: dict[str, FactSnapshot]) -> SignalResult:
    """Always evaluated. Fires when majority of canonical facts are missing."""
    poor: list[str] = []
    for name in _ALL_CANONICAL:
        f = pf.get(name)
        if f is None or f.value is None or f.confidence < _MIN_CONF_LOW:
            poor.append(name)
    fired = len(poor) >= _S13_THRESHOLD
    return SignalResult(
        signal_code="data_quality_warning",
        signal_name="Limited financial data coverage",
        category="data_quality",
        severity="informational",
        fired=fired,
        explanation=(
            f"{len(poor)} of {len(_ALL_CANONICAL)} standard financial fields "
            "were unavailable or below confidence threshold."
            if fired
            else f"{len(_ALL_CANONICAL) - len(poor)} of {len(_ALL_CANONICAL)} "
            "standard financial fields are available."
        ),
        evidence={
            "unavailable_facts": poor,
            "unavailable_count": len(poor),
            "total_facts": len(_ALL_CANONICAL),
        },
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_all_signals(
    primary_facts: dict[str, FactSnapshot],
    prior_facts: dict[str, FactSnapshot] | None,
    metrics: dict[str, MetricResult],
    company_profile: CompanyProfile,
    primary_period: PeriodSnapshot | None,
    prior_period: PeriodSnapshot | None,
) -> list[SignalResult]:
    """
    Evaluate all signals and return a list of non-None SignalResult instances.

    Signals that return None (insufficient data) are excluded from the output
    and the caller will not update their DB rows.

    S10 and S13 always return a result (never None).
    """
    pf = primary_facts
    pp = prior_facts or {}

    candidates: list[SignalResult | None] = [
        _s1(pf),
        _s2(pf, pp),
        _s3(metrics),
        _s4(metrics),
        _s5(metrics),
        _s6(metrics),
        _s7(metrics),
        _s8(metrics),
        _s9(company_profile),
        _s10(primary_period),
        _s11(pf, metrics),
        _s12(pf, pp),
        _s13(pf),
    ]

    return [s for s in candidates if s is not None]
