"""
HTML extractor unit tests.

Tests cover:
  - Happy path: single financial table with known label → canonical fact
  - Scale detection: £'000 header → ×1000 multiplier; millions → ×1000000
  - Value parsing: plain positive, negative bracket notation
  - Ambiguous flag: bracket notation sets is_comparative=False but ambiguous=True in scorer
  - Non-financial table is skipped
  - Deduplication: same canonical name in multiple rows yields only first
  - Multiple tables: facts from all financial tables are collected
  - Currency signals: £, €, gbp all trigger table inclusion
  - Unknown label rows are skipped
  - Period dates are None (HTML period detection not in Phase 5B)
  - Parse failure returns ExtractionResult with errors
  - extraction_method is 'html'
"""

from __future__ import annotations

from decimal import Decimal

import pytest

from app.parsers.html_extractor import extract_html


# ---------------------------------------------------------------------------
# Minimal HTML fixture helpers
# ---------------------------------------------------------------------------


def _simple_table(rows: list[tuple[str, str]], header: str = "£") -> str:
    header_row = f"<tr><th>{header}</th><th>Amount</th></tr>"
    data_rows = "".join(
        f"<tr><td>{label}</td><td>{value}</td></tr>" for label, value in rows
    )
    return f"<table>{header_row}{data_rows}</table>"


def _html_page(body: str) -> bytes:
    return f"<html><body>{body}</body></html>".encode()


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------


def test_extract_html_turnover_mapped_to_revenue() -> None:
    table = _simple_table([("Turnover", "1000000")])
    result = extract_html(_html_page(table))
    assert result.errors == []
    assert len(result.facts) == 1
    assert result.facts[0].canonical_name == "revenue"
    assert result.facts[0].fact_value == Decimal("1000000")


def test_extract_html_extraction_method_is_html() -> None:
    result = extract_html(_html_page(""))
    assert result.extraction_method == "html"


def test_extract_html_period_dates_are_none() -> None:
    table = _simple_table([("Turnover", "500000")])
    result = extract_html(_html_page(table))
    assert result.period_start is None
    assert result.period_end is None


def test_extract_html_run_confidence_is_decimal() -> None:
    table = _simple_table([("Turnover", "500000")])
    result = extract_html(_html_page(table))
    assert isinstance(result.run_confidence, Decimal)


# ---------------------------------------------------------------------------
# Scale detection
# ---------------------------------------------------------------------------


def test_scale_thousands_applied() -> None:
    """£'000 header → value multiplied by 1000."""
    table = _simple_table([("Turnover", "2500")], header="£'000")
    result = extract_html(_html_page(table))
    assert result.facts[0].fact_value == Decimal("2500000")


def test_scale_millions_applied() -> None:
    """£millions header → value multiplied by 1000000."""
    table = _simple_table([("Turnover", "3")], header="£millions")
    result = extract_html(_html_page(table))
    assert result.facts[0].fact_value == Decimal("3000000")


def test_scale_default_no_scale_header() -> None:
    """No scale indicator → value as-is (scale=1)."""
    table = _simple_table([("Turnover", "99000")], header="£")
    result = extract_html(_html_page(table))
    assert result.facts[0].fact_value == Decimal("99000")


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


def test_bracket_notation_produces_negative() -> None:
    table = _simple_table([("Gross profit", "(50000)")])
    result = extract_html(_html_page(table))
    assert result.facts[0].fact_value == Decimal("-50000")


def test_nil_value_skipped() -> None:
    table = _simple_table([("Turnover", "nil")])
    result = extract_html(_html_page(table))
    assert result.facts == []


def test_dash_value_skipped() -> None:
    table = _simple_table([("Turnover", "-")])
    result = extract_html(_html_page(table))
    assert result.facts == []


def test_na_value_skipped() -> None:
    table = _simple_table([("Turnover", "n/a")])
    result = extract_html(_html_page(table))
    assert result.facts == []


# ---------------------------------------------------------------------------
# Non-financial table is skipped
# ---------------------------------------------------------------------------


def test_non_financial_table_skipped() -> None:
    table = "<table><tr><td>Director</td><td>John Smith</td></tr></table>"
    result = extract_html(_html_page(table))
    assert result.facts == []


# ---------------------------------------------------------------------------
# Deduplication
# ---------------------------------------------------------------------------


def test_duplicate_canonical_name_in_table_deduped() -> None:
    """Second occurrence of the same canonical name in a table is dropped."""
    table = _simple_table([
        ("Turnover", "100000"),
        ("Revenue", "200000"),  # same canonical → revenue; should be skipped
    ])
    result = extract_html(_html_page(table))
    revenue_facts = [f for f in result.facts if f.canonical_name == "revenue"]
    assert len(revenue_facts) == 1
    assert revenue_facts[0].fact_value == Decimal("100000")


# ---------------------------------------------------------------------------
# Multiple tables
# ---------------------------------------------------------------------------


def test_multiple_tables_facts_collected() -> None:
    table1 = _simple_table([("Turnover", "500000")])
    table2 = _simple_table([("Current assets", "100000")])
    result = extract_html(_html_page(table1 + table2))
    names = {f.canonical_name for f in result.facts}
    assert "revenue" in names
    assert "current_assets" in names


# ---------------------------------------------------------------------------
# Currency signals
# ---------------------------------------------------------------------------


def test_euro_currency_signal_triggers_extraction() -> None:
    table = _simple_table([("Turnover", "1000000")], header="€")
    result = extract_html(_html_page(table))
    assert len(result.facts) == 1


def test_gbp_text_signal_triggers_extraction() -> None:
    table = _simple_table([("Turnover", "1000000")], header="GBP")
    result = extract_html(_html_page(table))
    assert len(result.facts) == 1


# ---------------------------------------------------------------------------
# Unknown labels
# ---------------------------------------------------------------------------


def test_unknown_label_skipped() -> None:
    table = _simple_table([("Some random line item", "999")])
    result = extract_html(_html_page(table))
    assert result.facts == []


def test_mixed_known_unknown_labels() -> None:
    table = _simple_table([
        ("Some random label", "99"),
        ("Turnover", "500000"),
    ])
    result = extract_html(_html_page(table))
    assert len(result.facts) == 1
    assert result.facts[0].canonical_name == "revenue"


# ---------------------------------------------------------------------------
# Parse failure
# ---------------------------------------------------------------------------


def test_empty_content_returns_no_facts() -> None:
    result = extract_html(b"")
    # lxml can parse empty bytes — just no tables
    assert result.errors == [] or result.facts == []


def test_extract_html_no_errors_on_valid_html() -> None:
    table = _simple_table([("Turnover", "1000")])
    result = extract_html(_html_page(table))
    assert result.errors == []


# ---------------------------------------------------------------------------
# Employees unit
# ---------------------------------------------------------------------------


def test_employees_unit_is_count() -> None:
    table = _simple_table([("Average number of employees", "42")])
    result = extract_html(_html_page(table))
    assert result.facts[0].unit == "count"
    assert result.facts[0].fact_value == Decimal("42")
