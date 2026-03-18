"""
Deterministic derived metric computation — Phase 6A.

Implements M1–M9 from docs/09-financial-analysis-spec.md.

All functions are pure: given the same inputs, they produce the same outputs.
No DB access.  No advisory language.  Null is never converted to zero.

Entry point:
    compute_all_metrics(primary_facts, prior_facts, primary_period, prior_period)
        -> list[MetricResult]
"""

from __future__ import annotations

from datetime import timedelta
from decimal import Decimal, InvalidOperation

from app.analytics.models import FactSnapshot, MetricResult, PeriodSnapshot
from app.parsers.confidence import confidence_band

METHODOLOGY_VERSION = "1.0.0"

# Minimum per-fact confidence required for any metric calculation.
_MIN_CONF = Decimal("0.40")

# Maximum period gap for growth metrics (18 months ≈ 548 days).
_MAX_GAP_DAYS = 548

# Range bounds for ratio metrics that get a range_anomaly warning.
_MARGIN_MAX = Decimal("10")
_MARGIN_MIN = Decimal("-10")
_REVENUE_GROWTH_MIN = Decimal("-1")
_REVENUE_GROWTH_MAX = Decimal("10")


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _min_conf(*confs: Decimal | None) -> Decimal | None:
    """Return the minimum of the provided confidence values, ignoring None.
    Returns None only when all inputs are None."""
    valid = [c for c in confs if c is not None]
    return min(valid) if valid else None


def _band(conf: Decimal | None) -> str:
    if conf is None:
        return "unavailable"
    return confidence_band(conf)


def _ok(f: FactSnapshot | None) -> bool:
    """True when the fact has a usable value and confidence >= minimum."""
    return (
        f is not None
        and f.value is not None
        and f.confidence >= _MIN_CONF
    )


def _null(key: str, unit: str, warning: str) -> MetricResult:
    return MetricResult(
        metric_key=key,
        metric_value=None,
        unit=unit,
        confidence=None,
        confidence_band="unavailable",
        warnings=[warning],
    )


def _period_gap_ok(primary: PeriodSnapshot, prior: PeriodSnapshot) -> bool:
    """True when the gap between prior.period_end and primary.period_start
    (or primary.period_end) is within MAX_GAP_DAYS."""
    reference = primary.period_start or primary.period_end
    gap = (reference - prior.period_end).days
    return gap <= _MAX_GAP_DAYS


# ---------------------------------------------------------------------------
# M1 — Gross profit margin
# ---------------------------------------------------------------------------


def _m1_gross_profit_margin(pf: dict[str, FactSnapshot]) -> MetricResult:
    key = "gross_profit_margin"
    rev = pf.get("revenue")
    gp = pf.get("gross_profit")
    if not _ok(rev) or not _ok(gp):
        return _null(key, "ratio", "missing_input")
    assert rev is not None and gp is not None  # narrowing for type checker
    if rev.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(rev.confidence, gp.confidence)
    val = gp.value / rev.value
    warnings = []
    if not (_MARGIN_MIN <= val <= _MARGIN_MAX):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M2 — Operating profit margin
# ---------------------------------------------------------------------------


def _m2_operating_profit_margin(pf: dict[str, FactSnapshot]) -> MetricResult:
    key = "operating_profit_margin"
    rev = pf.get("revenue")
    ebit = pf.get("operating_profit_loss")
    if not _ok(rev) or not _ok(ebit):
        return _null(key, "ratio", "missing_input")
    assert rev is not None and ebit is not None
    if rev.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(rev.confidence, ebit.confidence)
    val = ebit.value / rev.value
    warnings = []
    if not (_MARGIN_MIN <= val <= _MARGIN_MAX):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M3 — Net profit margin
# ---------------------------------------------------------------------------


def _m3_net_profit_margin(pf: dict[str, FactSnapshot]) -> MetricResult:
    key = "net_profit_margin"
    rev = pf.get("revenue")
    pat = pf.get("profit_loss_after_tax")
    if not _ok(rev) or not _ok(pat):
        return _null(key, "ratio", "missing_input")
    assert rev is not None and pat is not None
    if rev.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(rev.confidence, pat.confidence)
    val = pat.value / rev.value
    warnings = []
    if not (_MARGIN_MIN <= val <= _MARGIN_MAX):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M4 — Current ratio
# ---------------------------------------------------------------------------


def _m4_current_ratio(pf: dict[str, FactSnapshot]) -> MetricResult:
    key = "current_ratio"
    ca = pf.get("current_assets")
    cdwoy = pf.get("creditors_due_within_one_year")
    if not _ok(ca) or not _ok(cdwoy):
        return _null(key, "ratio", "missing_input")
    assert ca is not None and cdwoy is not None
    if cdwoy.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(ca.confidence, cdwoy.confidence)
    val = ca.value / cdwoy.value
    warnings = []
    if val > Decimal("100"):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M5 — Cash as a share of current assets
# ---------------------------------------------------------------------------


def _m5_cash_ratio(pf: dict[str, FactSnapshot]) -> MetricResult:
    key = "cash_ratio"
    cash = pf.get("cash_bank_on_hand")
    ca = pf.get("current_assets")
    if not _ok(cash) or not _ok(ca):
        return _null(key, "ratio", "missing_input")
    assert cash is not None and ca is not None
    if ca.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(cash.confidence, ca.confidence)
    val = cash.value / ca.value
    warnings = []
    if not (Decimal("0") <= val <= Decimal("1")):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M6 — Leverage proxy
# ---------------------------------------------------------------------------


def _m6_leverage(pf: dict[str, FactSnapshot]) -> MetricResult:
    """
    leverage = (CDWOY + CDAOY) / max(NAL, 1)

    Partial input rule (doc 09): if exactly one of CDWOY/CDAOY is present,
    substitute 0 for the missing one and add a 'partial_input' warning.
    Result is null when NAL <= 0 (misleading) or both creditor fields absent.
    """
    key = "leverage"
    cdwoy = pf.get("creditors_due_within_one_year")
    cdaoy = pf.get("creditors_due_after_one_year")
    nal = pf.get("net_assets_liabilities")

    cdwoy_ok = _ok(cdwoy)
    cdaoy_ok = _ok(cdaoy)

    if not cdwoy_ok and not cdaoy_ok:
        return _null(key, "ratio", "missing_input")
    if not _ok(nal):
        return _null(key, "ratio", "missing_input")

    assert nal is not None

    if nal.value is not None and nal.value <= 0:
        return _null(key, "ratio", "negative_equity")

    warnings = []
    cdwoy_val = Decimal("0")
    cdaoy_val = Decimal("0")
    confs: list[Decimal] = [nal.confidence]

    if cdwoy_ok:
        assert cdwoy is not None
        cdwoy_val = cdwoy.value  # type: ignore[assignment]
        confs.append(cdwoy.confidence)
    else:
        warnings.append("partial_input")

    if cdaoy_ok:
        assert cdaoy is not None
        cdaoy_val = cdaoy.value  # type: ignore[assignment]
        confs.append(cdaoy.confidence)
    else:
        if not cdwoy_ok:
            # Both absent — already caught above; belt-and-suspenders.
            return _null(key, "ratio", "missing_input")
        warnings.append("partial_input")

    conf = _min_conf(*confs)
    denominator = max(nal.value, Decimal("1"))  # type: ignore[arg-type]
    val = (cdwoy_val + cdaoy_val) / denominator
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M7 — Revenue growth (year-on-year)
# ---------------------------------------------------------------------------


def _m7_revenue_growth(
    pf: dict[str, FactSnapshot],
    prior_pf: dict[str, FactSnapshot],
    primary: PeriodSnapshot,
    prior: PeriodSnapshot,
) -> MetricResult:
    key = "revenue_growth"
    rev_c = pf.get("revenue")
    rev_p = prior_pf.get("revenue")
    if not _ok(rev_c) or not _ok(rev_p):
        return _null(key, "ratio", "missing_input")
    assert rev_c is not None and rev_p is not None
    if not _period_gap_ok(primary, prior):
        return _null(key, "ratio", "period_gap")
    if rev_p.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(rev_c.confidence, rev_p.confidence)
    val = (rev_c.value - rev_p.value) / abs(rev_p.value)
    warnings = []
    if not (_REVENUE_GROWTH_MIN <= val <= _REVENUE_GROWTH_MAX):
        warnings.append("range_anomaly")
    return MetricResult(key, val, "ratio", conf, _band(conf), warnings)


# ---------------------------------------------------------------------------
# M8 — Net assets growth (year-on-year)
# ---------------------------------------------------------------------------


def _m8_net_assets_growth(
    pf: dict[str, FactSnapshot],
    prior_pf: dict[str, FactSnapshot],
    primary: PeriodSnapshot,
    prior: PeriodSnapshot,
) -> MetricResult:
    key = "net_assets_growth"
    nal_c = pf.get("net_assets_liabilities")
    nal_p = prior_pf.get("net_assets_liabilities")
    if not _ok(nal_c) or not _ok(nal_p):
        return _null(key, "ratio", "missing_input")
    assert nal_c is not None and nal_p is not None
    if not _period_gap_ok(primary, prior):
        return _null(key, "ratio", "period_gap")
    if nal_p.value == 0:
        return _null(key, "ratio", "zero_denominator")
    conf = _min_conf(nal_c.confidence, nal_p.confidence)
    val = (nal_c.value - nal_p.value) / abs(nal_p.value)
    return MetricResult(key, val, "ratio", conf, _band(conf))


# ---------------------------------------------------------------------------
# M9 — Employee count change
# ---------------------------------------------------------------------------


def _m9_employee_growth(
    pf: dict[str, FactSnapshot],
    prior_pf: dict[str, FactSnapshot],
    primary: PeriodSnapshot,
    prior: PeriodSnapshot,
) -> MetricResult:
    key = "employee_growth"
    emp_c = pf.get("average_number_of_employees")
    emp_p = prior_pf.get("average_number_of_employees")
    if not _ok(emp_c) or not _ok(emp_p):
        return _null(key, "count", "missing_input")
    assert emp_c is not None and emp_p is not None
    if not _period_gap_ok(primary, prior):
        return _null(key, "count", "period_gap")
    conf = _min_conf(emp_c.confidence, emp_p.confidence)
    val = emp_c.value - emp_p.value  # type: ignore[operator]
    return MetricResult(key, val, "count", conf, _band(conf))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_all_metrics(
    primary_facts: dict[str, FactSnapshot],
    prior_facts: dict[str, FactSnapshot] | None,
    primary_period: PeriodSnapshot,
    prior_period: PeriodSnapshot | None,
) -> list[MetricResult]:
    """
    Compute all derived metrics for a company's primary period.

    prior_facts and prior_period may be None when no qualifying prior period
    exists; in that case, growth metrics (M7–M9) return null results.

    Returns a list of MetricResult — one per metric key, always present
    (null results are included so the DB row can be written/overwritten).
    """
    pf = primary_facts
    pp_facts = prior_facts or {}
    pp = prior_period  # may be None

    # Single-period metrics
    results: list[MetricResult] = [
        _m1_gross_profit_margin(pf),
        _m2_operating_profit_margin(pf),
        _m3_net_profit_margin(pf),
        _m4_current_ratio(pf),
        _m5_cash_ratio(pf),
        _m6_leverage(pf),
    ]

    # Growth metrics — require a prior period
    if pp is not None and pp_facts:
        results.extend([
            _m7_revenue_growth(pf, pp_facts, primary_period, pp),
            _m8_net_assets_growth(pf, pp_facts, primary_period, pp),
            _m9_employee_growth(pf, pp_facts, primary_period, pp),
        ])
    else:
        results.extend([
            _null("revenue_growth", "ratio", "no_prior_period"),
            _null("net_assets_growth", "ratio", "no_prior_period"),
            _null("employee_growth", "count", "no_prior_period"),
        ])

    return results
