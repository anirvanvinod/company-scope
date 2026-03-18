"""
Rule-based signal unit tests — Phase 6A.

Tests cover:
  - S1 negative net assets: fires/does not fire, suppressed on low confidence
  - S2 worsening: fires when both periods negative and declining
  - S3 revenue decline: severity high vs medium, does not fire above threshold
  - S4 liquidity pressure: fires below 1.0, not above
  - S5 severe liquidity: fires below 0.5
  - S6 cash concentration: both conditions required
  - S7 high leverage: fires above 3.0
  - S8 extreme leverage: fires above 10.0
  - S9 accounts overdue: fires from profile, suppressed for dissolved
  - S10 no recent accounts: fires when primary period absent or stale
  - S11 positive momentum: fires with growth > 10% and positive/absent EBIT
  - S12 consistent profitability: fires when both periods profitable
  - S13 data quality: fires when >= 6 facts missing/low confidence
  - compute_all_signals returns only non-None results
  - Signal suppression: returns None when confidence below threshold
  - fired=False results are returned (not None) for resolved signal logic
"""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from decimal import Decimal

import pytest

from app.analytics.models import (
    CompanyProfile,
    FactSnapshot,
    MetricResult,
    PeriodSnapshot,
)
from app.analytics.signals import (
    _s1, _s2, _s3, _s4, _s5, _s6, _s7, _s8, _s9, _s10, _s11, _s12, _s13,
    compute_all_signals,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(value: float | None, confidence: float = 0.80) -> FactSnapshot:
    return FactSnapshot(
        value=Decimal(str(value)) if value is not None else None,
        confidence=Decimal(str(confidence)),
    )


def _m(key: str, value: float | None, confidence: float = 0.80) -> MetricResult:
    from app.parsers.confidence import confidence_band
    conf = Decimal(str(confidence)) if value is not None else None
    band = confidence_band(conf) if conf is not None else "unavailable"
    return MetricResult(
        metric_key=key,
        metric_value=Decimal(str(value)) if value is not None else None,
        unit="ratio",
        confidence=conf,
        confidence_band=band,
    )


def _period(end: str = "2023-12-31") -> PeriodSnapshot:
    return PeriodSnapshot(
        period_id=uuid.uuid4(),
        period_end=date.fromisoformat(end),
        period_start=None,
        extraction_confidence=Decimal("0.85"),
        accounts_type="unknown",
    )


def _profile(overdue: bool | None = None, status: str = "active") -> CompanyProfile:
    return CompanyProfile(accounts_overdue=overdue, company_status=status)


# ---------------------------------------------------------------------------
# S1 — Negative net assets
# ---------------------------------------------------------------------------


def test_s1_fires_when_nal_negative() -> None:
    pf = {"net_assets_liabilities": _f(-100_000)}
    r = _s1(pf)
    assert r is not None
    assert r.fired is True
    assert r.signal_code == "negative_net_assets"
    assert r.severity == "high"


def test_s1_not_fired_when_nal_positive() -> None:
    pf = {"net_assets_liabilities": _f(500_000)}
    r = _s1(pf)
    assert r is not None
    assert r.fired is False


def test_s1_suppressed_when_confidence_too_low() -> None:
    pf = {"net_assets_liabilities": _f(-100_000, confidence=0.30)}
    r = _s1(pf)
    assert r is None


def test_s1_suppressed_when_no_nal() -> None:
    r = _s1({})
    assert r is None


def test_s1_suppressed_when_nal_value_is_none() -> None:
    pf = {"net_assets_liabilities": FactSnapshot(value=None, confidence=Decimal("0.80"))}
    r = _s1(pf)
    assert r is None


# ---------------------------------------------------------------------------
# S2 — Worsening negative net assets
# ---------------------------------------------------------------------------


def test_s2_fires_when_both_negative_and_declining() -> None:
    pf = {"net_assets_liabilities": _f(-200_000)}
    pp = {"net_assets_liabilities": _f(-100_000)}
    r = _s2(pf, pp)
    assert r is not None
    assert r.fired is True


def test_s2_not_fired_when_improving() -> None:
    pf = {"net_assets_liabilities": _f(-50_000)}
    pp = {"net_assets_liabilities": _f(-100_000)}
    r = _s2(pf, pp)
    assert r is not None
    assert r.fired is False


def test_s2_not_fired_when_current_positive() -> None:
    pf = {"net_assets_liabilities": _f(100_000)}
    pp = {"net_assets_liabilities": _f(-50_000)}
    r = _s2(pf, pp)
    assert r is not None
    assert r.fired is False


def test_s2_suppressed_when_medium_confidence_not_met() -> None:
    # S2 requires medium confidence (>= 0.65); both must qualify
    pf = {"net_assets_liabilities": _f(-200_000, confidence=0.60)}
    pp = {"net_assets_liabilities": _f(-100_000)}
    r = _s2(pf, pp)
    assert r is None


# ---------------------------------------------------------------------------
# S3 — Significant revenue decline
# ---------------------------------------------------------------------------


def test_s3_fires_medium_between_20_and_40_pct() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", -0.25)}
    r = _s3(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "medium"


def test_s3_fires_high_above_40_pct() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", -0.50)}
    r = _s3(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "high"


def test_s3_not_fired_above_threshold() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", -0.10)}
    r = _s3(metrics)
    assert r is not None
    assert r.fired is False


def test_s3_suppressed_when_metric_unavailable() -> None:
    r = _s3({})
    assert r is None


def test_s3_suppressed_when_metric_null_value() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", None)}
    r = _s3(metrics)
    assert r is None


# ---------------------------------------------------------------------------
# S4 — Liquidity pressure
# ---------------------------------------------------------------------------


def test_s4_fires_below_1() -> None:
    metrics = {"current_ratio": _m("current_ratio", 0.80)}
    r = _s4(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "medium"


def test_s4_not_fired_above_1() -> None:
    metrics = {"current_ratio": _m("current_ratio", 1.5)}
    r = _s4(metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S5 — Severe liquidity pressure
# ---------------------------------------------------------------------------


def test_s5_fires_below_05() -> None:
    metrics = {"current_ratio": _m("current_ratio", 0.30)}
    r = _s5(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "high"


def test_s5_not_fired_between_05_and_1() -> None:
    metrics = {"current_ratio": _m("current_ratio", 0.70)}
    r = _s5(metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S6 — Cash concentration risk
# ---------------------------------------------------------------------------


def test_s6_fires_when_both_conditions_met() -> None:
    metrics = {
        "cash_ratio": _m("cash_ratio", 0.03),
        "current_ratio": _m("current_ratio", 0.90),
    }
    r = _s6(metrics)
    assert r is not None
    assert r.fired is True


def test_s6_not_fired_when_only_low_cash() -> None:
    # current_ratio >= 1.2 — condition not met
    metrics = {
        "cash_ratio": _m("cash_ratio", 0.03),
        "current_ratio": _m("current_ratio", 1.5),
    }
    r = _s6(metrics)
    assert r is not None
    assert r.fired is False


def test_s6_not_fired_when_adequate_cash() -> None:
    metrics = {
        "cash_ratio": _m("cash_ratio", 0.20),
        "current_ratio": _m("current_ratio", 0.90),
    }
    r = _s6(metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S7 — High leverage
# ---------------------------------------------------------------------------


def test_s7_fires_above_3() -> None:
    metrics = {"leverage": _m("leverage", 4.0)}
    r = _s7(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "medium"


def test_s7_not_fired_at_3() -> None:
    metrics = {"leverage": _m("leverage", 3.0)}
    r = _s7(metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S8 — Extreme leverage
# ---------------------------------------------------------------------------


def test_s8_fires_above_10() -> None:
    metrics = {"leverage": _m("leverage", 12.0)}
    r = _s8(metrics)
    assert r is not None
    assert r.fired is True
    assert r.severity == "high"


def test_s8_not_fired_below_10() -> None:
    metrics = {"leverage": _m("leverage", 5.0)}
    r = _s8(metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S9 — Accounts overdue
# ---------------------------------------------------------------------------


def test_s9_fires_when_overdue() -> None:
    r = _s9(_profile(overdue=True))
    assert r is not None
    assert r.fired is True
    assert r.severity == "high"


def test_s9_not_fired_when_not_overdue() -> None:
    r = _s9(_profile(overdue=False))
    assert r is not None
    assert r.fired is False


def test_s9_suppressed_when_unknown() -> None:
    r = _s9(_profile(overdue=None))
    assert r is None


def test_s9_suppressed_for_dissolved_company() -> None:
    r = _s9(CompanyProfile(accounts_overdue=True, company_status="dissolved"))
    assert r is None


# ---------------------------------------------------------------------------
# S10 — No recent accounts
# ---------------------------------------------------------------------------


def test_s10_fires_when_no_primary_period() -> None:
    r = _s10(None)
    assert r.fired is True
    assert r.signal_code == "no_recent_accounts"


def test_s10_fires_when_period_older_than_24_months() -> None:
    stale_date = (date.today() - timedelta(days=800)).isoformat()
    r = _s10(_period(stale_date))
    assert r.fired is True


def test_s10_not_fired_when_period_recent() -> None:
    recent = (date.today() - timedelta(days=180)).isoformat()
    r = _s10(_period(recent))
    assert r.fired is False


def test_s10_always_returns_signal_result() -> None:
    # S10 never returns None
    assert _s10(None) is not None
    assert _s10(_period()) is not None


# ---------------------------------------------------------------------------
# S11 — Positive revenue momentum
# ---------------------------------------------------------------------------


def test_s11_fires_with_strong_growth_positive_ebit() -> None:
    pf = {"operating_profit_loss": _f(100_000)}
    metrics = {"revenue_growth": _m("revenue_growth", 0.20)}
    r = _s11(pf, metrics)
    assert r is not None
    assert r.fired is True


def test_s11_fires_with_growth_when_ebit_absent() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", 0.15)}
    r = _s11({}, metrics)
    assert r is not None
    assert r.fired is True


def test_s11_not_fired_below_10_pct() -> None:
    metrics = {"revenue_growth": _m("revenue_growth", 0.05)}
    r = _s11({}, metrics)
    assert r is not None
    assert r.fired is False


def test_s11_not_fired_when_ebit_negative() -> None:
    pf = {"operating_profit_loss": _f(-50_000)}
    metrics = {"revenue_growth": _m("revenue_growth", 0.30)}
    r = _s11(pf, metrics)
    assert r is not None
    assert r.fired is False


# ---------------------------------------------------------------------------
# S12 — Consistent profitability
# ---------------------------------------------------------------------------


def test_s12_fires_when_both_profitable() -> None:
    pf = {"profit_loss_after_tax": _f(200_000)}
    pp = {"profit_loss_after_tax": _f(150_000)}
    r = _s12(pf, pp)
    assert r is not None
    assert r.fired is True
    assert r.severity == "informational"


def test_s12_not_fired_when_current_loss() -> None:
    pf = {"profit_loss_after_tax": _f(-10_000)}
    pp = {"profit_loss_after_tax": _f(150_000)}
    r = _s12(pf, pp)
    assert r is not None
    assert r.fired is False


def test_s12_suppressed_when_medium_confidence_not_met() -> None:
    pf = {"profit_loss_after_tax": _f(200_000, confidence=0.50)}
    pp = {"profit_loss_after_tax": _f(150_000)}
    r = _s12(pf, pp)
    assert r is None


# ---------------------------------------------------------------------------
# S13 — Data quality warning
# ---------------------------------------------------------------------------


def test_s13_fires_when_majority_missing() -> None:
    # Only 2 facts available — 10 missing → fires
    pf = {"revenue": _f(100_000), "current_assets": _f(50_000)}
    r = _s13(pf)
    assert r.fired is True
    assert r.signal_code == "data_quality_warning"
    assert r.evidence["unavailable_count"] >= 6


def test_s13_not_fired_when_adequate_coverage() -> None:
    # All 12 facts present with good confidence
    all_facts = {
        "revenue": _f(1_000_000),
        "gross_profit": _f(400_000),
        "operating_profit_loss": _f(200_000),
        "profit_loss_after_tax": _f(150_000),
        "current_assets": _f(300_000),
        "fixed_assets": _f(100_000),
        "total_assets_less_current_liabilities": _f(400_000),
        "creditors_due_within_one_year": _f(100_000),
        "creditors_due_after_one_year": _f(50_000),
        "net_assets_liabilities": _f(500_000),
        "cash_bank_on_hand": _f(80_000),
        "average_number_of_employees": _f(30),
    }
    r = _s13(all_facts)
    assert r.fired is False


def test_s13_always_returns_signal_result() -> None:
    assert _s13({}) is not None


def test_s13_counts_low_confidence_as_poor() -> None:
    """Facts with confidence < 0.40 count as missing for S13."""
    pf = {"revenue": _f(1_000_000, confidence=0.20)}  # below threshold
    r = _s13(pf)
    assert r.fired is True


# ---------------------------------------------------------------------------
# compute_all_signals — integration
# ---------------------------------------------------------------------------


def test_compute_all_signals_returns_list() -> None:
    results = compute_all_signals({}, None, {}, _profile(), None, None)
    assert isinstance(results, list)


def test_compute_all_signals_excludes_none_results() -> None:
    """Signals with insufficient data (None) should not appear in output."""
    results = compute_all_signals({}, None, {}, _profile(), None, None)
    for r in results:
        assert r is not None


def test_compute_all_signals_s10_and_s13_always_present() -> None:
    """S10 and S13 always produce a result — never suppressed."""
    results = compute_all_signals({}, None, {}, _profile(), None, None)
    codes = {r.signal_code for r in results}
    assert "no_recent_accounts" in codes
    assert "data_quality_warning" in codes


def test_compute_all_signals_accounts_overdue_appears() -> None:
    profile = CompanyProfile(accounts_overdue=True, company_status="active")
    period = _period()
    results = compute_all_signals(
        {"net_assets_liabilities": _f(100_000)},
        None,
        {},
        profile,
        period,
        None,
    )
    overdue = [r for r in results if r.signal_code == "accounts_overdue"]
    assert len(overdue) == 1
    assert overdue[0].fired is True
