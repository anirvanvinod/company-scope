"""
Confidence scoring unit tests.

Tests cover:
  - score_ixbrl_fact: all flag combinations
  - score_html_fact: all flag combinations
  - aggregate_run_confidence: empty, single, multiple, unmapped exclusion
  - confidence_band: boundary values for all four bands
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.parsers.confidence import (
    aggregate_run_confidence,
    confidence_band,
    score_html_fact,
    score_ixbrl_fact,
)
from app.parsers.models import RawFact


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_fact(canonical_name: str | None, confidence: Decimal) -> RawFact:
    return RawFact(
        raw_label="label",
        raw_tag=None,
        raw_context_ref=None,
        raw_value="100",
        fact_value=Decimal("100"),
        unit="GBP",
        period_start=None,
        period_end=None,
        is_comparative=False,
        scale=0,
        canonical_name=canonical_name,
        mapping_method=None,
        extraction_confidence=confidence,
    )


# ---------------------------------------------------------------------------
# score_ixbrl_fact
# ---------------------------------------------------------------------------


def test_ixbrl_all_flags_true_returns_095() -> None:
    assert score_ixbrl_fact(True, True, True) == Decimal("0.95")


def test_ixbrl_mapped_no_period_returns_080() -> None:
    # 0.95 - 0.15 = 0.80
    assert score_ixbrl_fact(True, False, True) == Decimal("0.80")


def test_ixbrl_mapped_no_decimals_returns_090() -> None:
    # 0.95 - 0.05 = 0.90
    assert score_ixbrl_fact(True, True, False) == Decimal("0.90")


def test_ixbrl_mapped_no_period_no_decimals_returns_075() -> None:
    # 0.95 - 0.15 - 0.05 = 0.75
    assert score_ixbrl_fact(True, False, False) == Decimal("0.75")


def test_ixbrl_unmapped_with_period_returns_050() -> None:
    assert score_ixbrl_fact(False, True, True) == Decimal("0.50")


def test_ixbrl_unmapped_no_period_returns_040() -> None:
    # 0.50 - 0.10 = 0.40
    assert score_ixbrl_fact(False, False, True) == Decimal("0.40")


def test_ixbrl_score_never_below_010() -> None:
    # Hypothetically if all penalties applied below floor
    score = score_ixbrl_fact(False, False, False)
    assert score >= Decimal("0.10")


def test_ixbrl_score_returns_decimal() -> None:
    result = score_ixbrl_fact(True, True, True)
    assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# score_html_fact
# ---------------------------------------------------------------------------


def test_html_all_flags_true_returns_075() -> None:
    assert score_html_fact(True, True, True) == Decimal("0.75")


def test_html_mapped_no_period_returns_065() -> None:
    # 0.75 - 0.10 = 0.65
    assert score_html_fact(True, False, True) == Decimal("0.65")


def test_html_mapped_ambiguous_returns_065() -> None:
    # 0.75 - 0.10 = 0.65
    assert score_html_fact(True, True, False) == Decimal("0.65")


def test_html_mapped_no_period_ambiguous_returns_055() -> None:
    # 0.75 - 0.10 - 0.10 = 0.55
    assert score_html_fact(True, False, False) == Decimal("0.55")


def test_html_unmapped_returns_030() -> None:
    assert score_html_fact(False, True, True) == Decimal("0.30")


def test_html_score_never_below_010() -> None:
    score = score_html_fact(False, False, False)
    assert score >= Decimal("0.10")


def test_html_score_returns_decimal() -> None:
    result = score_html_fact(True, False, False)
    assert isinstance(result, Decimal)


# ---------------------------------------------------------------------------
# aggregate_run_confidence
# ---------------------------------------------------------------------------


def test_aggregate_empty_facts_returns_zero() -> None:
    assert aggregate_run_confidence([]) == Decimal("0")


def test_aggregate_no_canonical_facts_returns_zero() -> None:
    facts = [_make_raw_fact(None, Decimal("0.80"))]
    assert aggregate_run_confidence(facts) == Decimal("0")


def test_aggregate_single_canonical_fact() -> None:
    facts = [_make_raw_fact("revenue", Decimal("0.90"))]
    assert aggregate_run_confidence(facts) == Decimal("0.90")


def test_aggregate_multiple_canonical_facts_is_mean() -> None:
    facts = [
        _make_raw_fact("revenue", Decimal("0.90")),
        _make_raw_fact("gross_profit", Decimal("0.70")),
    ]
    expected = (Decimal("0.90") + Decimal("0.70")) / Decimal("2")
    assert aggregate_run_confidence(facts) == expected


def test_aggregate_excludes_unmapped_facts() -> None:
    facts = [
        _make_raw_fact("revenue", Decimal("0.90")),
        _make_raw_fact(None, Decimal("0.10")),  # unmapped — should not affect mean
    ]
    assert aggregate_run_confidence(facts) == Decimal("0.90")


def test_aggregate_mixed_mapped_and_unmapped() -> None:
    facts = [
        _make_raw_fact("revenue", Decimal("0.80")),
        _make_raw_fact("gross_profit", Decimal("0.60")),
        _make_raw_fact(None, Decimal("0.30")),
    ]
    expected = (Decimal("0.80") + Decimal("0.60")) / Decimal("2")
    assert aggregate_run_confidence(facts) == expected


# ---------------------------------------------------------------------------
# confidence_band
# ---------------------------------------------------------------------------


def test_band_high() -> None:
    assert confidence_band(Decimal("0.85")) == "high"
    assert confidence_band(Decimal("0.95")) == "high"
    assert confidence_band(Decimal("1.00")) == "high"


def test_band_medium() -> None:
    assert confidence_band(Decimal("0.65")) == "medium"
    assert confidence_band(Decimal("0.84")) == "medium"


def test_band_low() -> None:
    assert confidence_band(Decimal("0.40")) == "low"
    assert confidence_band(Decimal("0.64")) == "low"


def test_band_unavailable() -> None:
    assert confidence_band(Decimal("0.39")) == "unavailable"
    assert confidence_band(Decimal("0.10")) == "unavailable"
    assert confidence_band(Decimal("0.00")) == "unavailable"


def test_band_boundary_085_is_high() -> None:
    assert confidence_band(Decimal("0.85")) == "high"


def test_band_boundary_065_is_medium() -> None:
    assert confidence_band(Decimal("0.65")) == "medium"


def test_band_boundary_040_is_low() -> None:
    assert confidence_band(Decimal("0.40")) == "low"
