"""
Tests for the Phase 6B deterministic template fallback.

Coverage:
- summary_short is populated and within 280 chars
- source is always "template"
- standard caveat is always included
- fired signals appear in key_observations
- narrative paragraphs are produced for available data
- data_quality_note populated when facts_available < 6
- accounts_type caveat appended for micro-entity / dormant
- missing values produce no errors (no KeyError, no AttributeError)
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.analytics.ai_models import (
    AnalysisContext,
    CompanyInfo,
    DataQualityInfo,
    FactValue,
    PrimaryPeriodInfo,
    SignalInfo,
)
from app.analytics.fallback import _STANDARD_CAVEAT, generate_template_summary


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_ctx(
    *,
    revenue: Decimal | None = Decimal("4_200_000"),
    net_profit: Decimal | None = Decimal("521_000"),
    accounts_type: str | None = None,
    signals: list[SignalInfo] | None = None,
    facts_available: int = 10,
    has_prior: bool = True,
    revenue_growth: Decimal | None = Decimal("12.5"),
    current_ratio: Decimal | None = Decimal("1.80"),
    confidence_band: str = "high",
) -> AnalysisContext:
    return AnalysisContext(
        company=CompanyInfo(
            company_number="01234567",
            company_name="Test Trading Ltd",
            company_status="active",
            company_type="ltd",
            sic_codes=["62012"],
            date_of_creation="2010-06-01",
            accounts_overdue=False,
        ),
        primary_period=PrimaryPeriodInfo(
            period_end="2023-12-31",
            period_start="2023-01-01",
            accounts_type=accounts_type,
            currency_code="GBP",
            extraction_confidence=Decimal("0.90"),
            confidence_band=confidence_band,
        ),
        facts={
            "revenue": FactValue(value=revenue, confidence=Decimal("0.90"), band="high"),
            "profit_loss_after_tax": FactValue(value=net_profit, confidence=Decimal("0.88"), band="high"),
            "current_assets": FactValue(value=Decimal("1_200_000"), confidence=Decimal("0.85"), band="high"),
            "creditors_due_within_one_year": FactValue(value=Decimal("666_000"), confidence=Decimal("0.85"), band="high"),
            "net_assets_liabilities": FactValue(value=Decimal("800_000"), confidence=Decimal("0.87"), band="high"),
            "cash_bank_on_hand": FactValue(value=Decimal("300_000"), confidence=Decimal("0.85"), band="high"),
        },
        derived_metrics={
            "current_ratio": FactValue(value=current_ratio, confidence=Decimal("0.85"), band="high"),
            "net_profit_margin": FactValue(value=Decimal("12.4"), confidence=Decimal("0.88"), band="high"),
            "revenue_growth": FactValue(value=revenue_growth, confidence=Decimal("0.80"), band="high"),
        },
        signals=signals or [],
        data_quality=DataQualityInfo(
            facts_available_count=facts_available,
            facts_total=12,
            primary_period_confidence_band=confidence_band,
            has_prior_period=has_prior,
            warnings=[],
        ),
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_source_is_always_template():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    assert result.source == "template"


def test_summary_short_within_280_chars():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    assert len(result.summary_short) <= 280


def test_summary_short_contains_company_number():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    assert "01234567" in result.summary_short


def test_standard_caveat_always_present():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    assert _STANDARD_CAVEAT in result.caveats


def test_financial_overview_paragraph_present():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    topics = [p.topic for p in result.narrative_paragraphs]
    assert "financial_overview" in topics


def test_liquidity_paragraph_present_when_data_available():
    ctx = _make_ctx()
    result = generate_template_summary(ctx)
    topics = [p.topic for p in result.narrative_paragraphs]
    assert "liquidity" in topics


def test_growth_paragraph_present_with_prior_period():
    ctx = _make_ctx(has_prior=True)
    result = generate_template_summary(ctx)
    topics = [p.topic for p in result.narrative_paragraphs]
    assert "growth" in topics


def test_growth_paragraph_absent_without_prior_period():
    ctx = _make_ctx(has_prior=False)
    result = generate_template_summary(ctx)
    topics = [p.topic for p in result.narrative_paragraphs]
    assert "growth" not in topics


def test_fired_signals_appear_in_key_observations():
    signals = [
        SignalInfo(
            signal_key="S01_ACCOUNTS_OVERDUE",
            severity="medium",
            fired=True,
            evidence_summary="Accounts are overdue at Companies House",
        ),
        SignalInfo(
            signal_key="S02_NEGATIVE_NET_ASSETS",
            severity="high",
            fired=True,
            evidence_summary="Net assets are negative",
        ),
    ]
    ctx = _make_ctx(signals=signals)
    result = generate_template_summary(ctx)
    assert len(result.key_observations) == 2
    refs = [o.evidence_ref for o in result.key_observations]
    assert "S01_ACCOUNTS_OVERDUE" in refs
    assert "S02_NEGATIVE_NET_ASSETS" in refs


def test_unfired_signals_not_in_key_observations():
    signals = [
        SignalInfo(
            signal_key="S01_ACCOUNTS_OVERDUE",
            severity="medium",
            fired=False,
            evidence_summary="Accounts are not overdue",
        ),
    ]
    ctx = _make_ctx(signals=signals)
    result = generate_template_summary(ctx)
    assert result.key_observations == []


def test_key_observations_capped_at_five():
    signals = [
        SignalInfo(
            signal_key=f"S{i:02d}_SIGNAL",
            severity="low",
            fired=True,
            evidence_summary=f"Signal {i} fired",
        )
        for i in range(8)
    ]
    ctx = _make_ctx(signals=signals)
    result = generate_template_summary(ctx)
    assert len(result.key_observations) <= 5


def test_data_quality_note_populated_when_few_facts():
    ctx = _make_ctx(facts_available=3)
    result = generate_template_summary(ctx)
    assert result.data_quality_note is not None
    assert "3" in result.data_quality_note


def test_data_quality_note_absent_when_many_facts():
    ctx = _make_ctx(facts_available=10)
    result = generate_template_summary(ctx)
    assert result.data_quality_note is None


def test_micro_entity_caveat_appended():
    ctx = _make_ctx(accounts_type="micro-entity")
    result = generate_template_summary(ctx)
    assert any("micro-entity" in c for c in result.caveats)


def test_dormant_caveat_appended():
    ctx = _make_ctx(accounts_type="dormant")
    result = generate_template_summary(ctx)
    assert any("dormant" in c for c in result.caveats)


def test_none_revenue_does_not_raise():
    ctx = _make_ctx(revenue=None, net_profit=None)
    result = generate_template_summary(ctx)
    assert "not available" in result.summary_short


def test_none_metrics_do_not_raise():
    ctx = _make_ctx(current_ratio=None, revenue_growth=None)
    result = generate_template_summary(ctx)
    assert result.source == "template"


def test_no_signals_produces_empty_observations():
    ctx = _make_ctx(signals=[])
    result = generate_template_summary(ctx)
    assert result.key_observations == []


def test_low_confidence_band_note_in_overview():
    ctx = _make_ctx(confidence_band="low")
    result = generate_template_summary(ctx)
    overview = next(
        p for p in result.narrative_paragraphs if p.topic == "financial_overview"
    )
    assert overview.confidence_note is not None
    assert "low" in overview.confidence_note
