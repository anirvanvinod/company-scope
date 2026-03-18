"""
Derived metrics unit tests — Phase 6A.

Tests cover:
  - M1 gross profit margin: normal, zero revenue, null input, low confidence
  - M2 operating profit margin: normal, null input
  - M3 net profit margin: normal, zero revenue
  - M4 current ratio: normal, zero denominator, null input
  - M5 cash ratio: normal, range anomaly warning
  - M6 leverage: normal, partial input (one creditor null), negative equity → null
  - M7 revenue growth: normal, period gap, zero prior revenue, null prior
  - M8 net assets growth: normal, period gap
  - M9 employee growth: normal, null input
  - confidence propagation: min of inputs, not averaged
  - range_anomaly warnings
  - no_prior_period null results when prior is absent
  - compute_all_metrics returns all 9 metric keys
"""

from __future__ import annotations

import uuid
from datetime import date
from decimal import Decimal

import pytest

from app.analytics.metrics import (
    METHODOLOGY_VERSION,
    _m1_gross_profit_margin,
    _m2_operating_profit_margin,
    _m3_net_profit_margin,
    _m4_current_ratio,
    _m5_cash_ratio,
    _m6_leverage,
    _m7_revenue_growth,
    _m8_net_assets_growth,
    _m9_employee_growth,
    compute_all_metrics,
)
from app.analytics.models import FactSnapshot, PeriodSnapshot


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _f(value: float | None, confidence: float = 0.90) -> FactSnapshot:
    return FactSnapshot(
        value=Decimal(str(value)) if value is not None else None,
        confidence=Decimal(str(confidence)),
    )


def _period(
    end: str = "2023-12-31",
    start: str = "2023-01-01",
) -> PeriodSnapshot:
    return PeriodSnapshot(
        period_id=uuid.uuid4(),
        period_end=date.fromisoformat(end),
        period_start=date.fromisoformat(start),
        extraction_confidence=Decimal("0.85"),
        accounts_type="unknown",
    )


# ---------------------------------------------------------------------------
# M1 — Gross profit margin
# ---------------------------------------------------------------------------


def test_m1_normal() -> None:
    pf = {"revenue": _f(1_000_000), "gross_profit": _f(400_000)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_key == "gross_profit_margin"
    assert r.metric_value == Decimal("0.4")
    assert r.unit == "ratio"
    assert r.confidence is not None
    assert r.warnings == []


def test_m1_zero_revenue() -> None:
    pf = {"revenue": _f(0), "gross_profit": _f(100)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_value is None
    assert "zero_denominator" in r.warnings


def test_m1_null_revenue() -> None:
    pf = {"gross_profit": _f(100)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_value is None
    assert "missing_input" in r.warnings


def test_m1_null_gross_profit() -> None:
    pf = {"revenue": _f(1_000_000)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_value is None


def test_m1_low_confidence_suppressed() -> None:
    pf = {"revenue": _f(1_000_000, confidence=0.30), "gross_profit": _f(400_000)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_value is None
    assert "missing_input" in r.warnings


def test_m1_range_anomaly_warning() -> None:
    """Margin > 10 triggers range_anomaly."""
    pf = {"revenue": _f(10), "gross_profit": _f(200)}
    r = _m1_gross_profit_margin(pf)
    assert r.metric_value is not None
    assert "range_anomaly" in r.warnings


# ---------------------------------------------------------------------------
# M2 — Operating profit margin
# ---------------------------------------------------------------------------


def test_m2_normal() -> None:
    pf = {"revenue": _f(500_000), "operating_profit_loss": _f(75_000)}
    r = _m2_operating_profit_margin(pf)
    assert r.metric_key == "operating_profit_margin"
    assert r.metric_value == Decimal("75000") / Decimal("500000")


def test_m2_missing_ebit() -> None:
    pf = {"revenue": _f(500_000)}
    r = _m2_operating_profit_margin(pf)
    assert r.metric_value is None


# ---------------------------------------------------------------------------
# M3 — Net profit margin
# ---------------------------------------------------------------------------


def test_m3_normal() -> None:
    pf = {"revenue": _f(1_000_000), "profit_loss_after_tax": _f(-50_000)}
    r = _m3_net_profit_margin(pf)
    assert r.metric_key == "net_profit_margin"
    assert r.metric_value == Decimal("-0.05")


def test_m3_zero_revenue() -> None:
    pf = {"revenue": _f(0), "profit_loss_after_tax": _f(100)}
    r = _m3_net_profit_margin(pf)
    assert r.metric_value is None
    assert "zero_denominator" in r.warnings


# ---------------------------------------------------------------------------
# M4 — Current ratio
# ---------------------------------------------------------------------------


def test_m4_normal() -> None:
    pf = {"current_assets": _f(200_000), "creditors_due_within_one_year": _f(100_000)}
    r = _m4_current_ratio(pf)
    assert r.metric_key == "current_ratio"
    assert r.metric_value == Decimal("2.0")
    assert r.warnings == []


def test_m4_zero_creditors() -> None:
    pf = {"current_assets": _f(200_000), "creditors_due_within_one_year": _f(0)}
    r = _m4_current_ratio(pf)
    assert r.metric_value is None
    assert "zero_denominator" in r.warnings


def test_m4_null_current_assets() -> None:
    pf = {"creditors_due_within_one_year": _f(100_000)}
    r = _m4_current_ratio(pf)
    assert r.metric_value is None


# ---------------------------------------------------------------------------
# M5 — Cash ratio
# ---------------------------------------------------------------------------


def test_m5_normal() -> None:
    pf = {"cash_bank_on_hand": _f(50_000), "current_assets": _f(200_000)}
    r = _m5_cash_ratio(pf)
    assert r.metric_key == "cash_ratio"
    assert r.metric_value == Decimal("0.25")
    assert r.warnings == []


def test_m5_range_anomaly_negative_cash() -> None:
    """Negative cash (unusual) triggers range_anomaly."""
    pf = {"cash_bank_on_hand": _f(-1_000), "current_assets": _f(200_000)}
    r = _m5_cash_ratio(pf)
    assert r.metric_value is not None
    assert "range_anomaly" in r.warnings


# ---------------------------------------------------------------------------
# M6 — Leverage proxy
# ---------------------------------------------------------------------------


def test_m6_normal_both_creditors() -> None:
    pf = {
        "creditors_due_within_one_year": _f(100_000),
        "creditors_due_after_one_year": _f(200_000),
        "net_assets_liabilities": _f(300_000),
    }
    r = _m6_leverage(pf)
    assert r.metric_key == "leverage"
    assert r.metric_value == Decimal("1.0")
    assert r.warnings == []


def test_m6_partial_input_cdaoy_missing() -> None:
    """Only CDWOY present — uses 0 for CDAOY, adds partial_input warning."""
    pf = {
        "creditors_due_within_one_year": _f(100_000),
        "net_assets_liabilities": _f(200_000),
    }
    r = _m6_leverage(pf)
    assert r.metric_value is not None
    assert "partial_input" in r.warnings


def test_m6_negative_equity_returns_null() -> None:
    pf = {
        "creditors_due_within_one_year": _f(100_000),
        "creditors_due_after_one_year": _f(50_000),
        "net_assets_liabilities": _f(-10_000),
    }
    r = _m6_leverage(pf)
    assert r.metric_value is None
    assert "negative_equity" in r.warnings


def test_m6_both_creditors_missing() -> None:
    pf = {"net_assets_liabilities": _f(300_000)}
    r = _m6_leverage(pf)
    assert r.metric_value is None
    assert "missing_input" in r.warnings


# ---------------------------------------------------------------------------
# M7 — Revenue growth
# ---------------------------------------------------------------------------


def test_m7_normal() -> None:
    primary = _period("2023-12-31", "2023-01-01")
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"revenue": _f(1_200_000)}
    pp = {"revenue": _f(1_000_000)}
    r = _m7_revenue_growth(pf, pp, primary, prior)
    assert r.metric_key == "revenue_growth"
    assert r.metric_value == Decimal("0.2")
    assert r.warnings == []


def test_m7_period_gap_too_large() -> None:
    primary = _period("2023-12-31", "2023-01-01")
    # Prior period ends 2 years before primary starts — > 548 days
    prior = _period("2020-12-31", "2020-01-01")
    pf = {"revenue": _f(1_000_000)}
    pp = {"revenue": _f(800_000)}
    r = _m7_revenue_growth(pf, pp, primary, prior)
    assert r.metric_value is None
    assert "period_gap" in r.warnings


def test_m7_zero_prior_revenue() -> None:
    primary = _period("2023-12-31", "2023-01-01")
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"revenue": _f(500_000)}
    pp = {"revenue": _f(0)}
    r = _m7_revenue_growth(pf, pp, primary, prior)
    assert r.metric_value is None
    assert "zero_denominator" in r.warnings


def test_m7_null_prior_revenue() -> None:
    primary = _period("2023-12-31", "2023-01-01")
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"revenue": _f(500_000)}
    pp: dict = {}
    r = _m7_revenue_growth(pf, pp, primary, prior)
    assert r.metric_value is None
    assert "missing_input" in r.warnings


def test_m7_range_anomaly_extreme_growth() -> None:
    primary = _period("2023-12-31", "2023-01-01")
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"revenue": _f(12_000_000)}
    pp = {"revenue": _f(1_000_000)}
    r = _m7_revenue_growth(pf, pp, primary, prior)
    assert r.metric_value is not None
    assert "range_anomaly" in r.warnings


# ---------------------------------------------------------------------------
# M8 — Net assets growth
# ---------------------------------------------------------------------------


def test_m8_normal() -> None:
    primary = _period()
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"net_assets_liabilities": _f(500_000)}
    pp = {"net_assets_liabilities": _f(400_000)}
    r = _m8_net_assets_growth(pf, pp, primary, prior)
    assert r.metric_key == "net_assets_growth"
    assert r.metric_value == Decimal("0.25")


def test_m8_period_gap() -> None:
    primary = _period()
    prior = _period("2020-12-31", "2020-01-01")
    pf = {"net_assets_liabilities": _f(500_000)}
    pp = {"net_assets_liabilities": _f(400_000)}
    r = _m8_net_assets_growth(pf, pp, primary, prior)
    assert r.metric_value is None
    assert "period_gap" in r.warnings


# ---------------------------------------------------------------------------
# M9 — Employee growth
# ---------------------------------------------------------------------------


def test_m9_normal() -> None:
    primary = _period()
    prior = _period("2022-12-31", "2022-01-01")
    pf = {"average_number_of_employees": _f(25)}
    pp = {"average_number_of_employees": _f(20)}
    r = _m9_employee_growth(pf, pp, primary, prior)
    assert r.metric_key == "employee_growth"
    assert r.metric_value == Decimal("5")
    assert r.unit == "count"


def test_m9_null_input() -> None:
    primary = _period()
    prior = _period("2022-12-31", "2022-01-01")
    r = _m9_employee_growth({}, {}, primary, prior)
    assert r.metric_value is None
    assert "missing_input" in r.warnings


# ---------------------------------------------------------------------------
# Confidence propagation
# ---------------------------------------------------------------------------


def test_confidence_is_minimum_of_inputs() -> None:
    pf = {"revenue": _f(1_000_000, confidence=0.85), "gross_profit": _f(400_000, confidence=0.65)}
    r = _m1_gross_profit_margin(pf)
    assert r.confidence == Decimal("0.65")


def test_confidence_is_not_average() -> None:
    pf = {"revenue": _f(1_000_000, confidence=0.95), "gross_profit": _f(400_000, confidence=0.45)}
    r = _m1_gross_profit_margin(pf)
    # Should be 0.45 (min), not (0.95+0.45)/2 = 0.70
    assert r.confidence == Decimal("0.45")


def test_confidence_band_high() -> None:
    pf = {"revenue": _f(1_000_000, confidence=0.90), "gross_profit": _f(400_000, confidence=0.90)}
    r = _m1_gross_profit_margin(pf)
    assert r.confidence_band == "high"


def test_confidence_band_unavailable_for_null_metric() -> None:
    r = _m1_gross_profit_margin({})
    assert r.confidence_band == "unavailable"
    assert r.confidence is None


# ---------------------------------------------------------------------------
# compute_all_metrics — integration
# ---------------------------------------------------------------------------


def test_compute_all_metrics_returns_all_keys() -> None:
    primary = _period()
    prior = _period("2022-12-31", "2022-01-01")
    pf = {
        "revenue": _f(1_000_000),
        "gross_profit": _f(400_000),
        "operating_profit_loss": _f(200_000),
        "profit_loss_after_tax": _f(150_000),
        "current_assets": _f(300_000),
        "creditors_due_within_one_year": _f(100_000),
        "creditors_due_after_one_year": _f(50_000),
        "net_assets_liabilities": _f(500_000),
        "cash_bank_on_hand": _f(80_000),
        "average_number_of_employees": _f(30),
    }
    pp = {
        "revenue": _f(900_000),
        "net_assets_liabilities": _f(450_000),
        "average_number_of_employees": _f(25),
    }
    results = compute_all_metrics(pf, pp, primary, prior)
    keys = {r.metric_key for r in results}
    expected = {
        "gross_profit_margin", "operating_profit_margin", "net_profit_margin",
        "current_ratio", "cash_ratio", "leverage",
        "revenue_growth", "net_assets_growth", "employee_growth",
    }
    assert keys == expected


def test_compute_all_metrics_no_prior_period_returns_null_growth() -> None:
    primary = _period()
    results = compute_all_metrics({}, None, primary, None)
    growth_results = {r.metric_key: r for r in results if "growth" in r.metric_key}
    for r in growth_results.values():
        assert r.metric_value is None
        assert "no_prior_period" in r.warnings


def test_methodology_version_constant() -> None:
    assert METHODOLOGY_VERSION == "1.0.0"
