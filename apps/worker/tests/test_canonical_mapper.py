"""
Canonical mapper unit tests.

Tests cover:
  - map_tag: direct tag-name to canonical name lookups
  - map_tag: namespace prefix stripping (done by caller, not mapper)
  - map_tag: normalisation (case, underscores, hyphens)
  - map_tag: unmapped tags return None
  - map_label: direct label lookups
  - map_label: whitespace normalisation
  - map_label: case-insensitive lookup
  - map_label: unmapped labels return None
  - All 12 canonical names are reachable via both paths
"""

from __future__ import annotations

import pytest

from app.parsers.canonical_mapper import map_label, map_tag

ALL_CANONICAL = {
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
}


# ---------------------------------------------------------------------------
# map_tag — direct lookups
# ---------------------------------------------------------------------------


def test_map_tag_turnover_returns_revenue() -> None:
    assert map_tag("Turnover") == "revenue"


def test_map_tag_revenue_returns_revenue() -> None:
    assert map_tag("Revenue") == "revenue"


def test_map_tag_gross_profit() -> None:
    assert map_tag("GrossProfit") == "gross_profit"


def test_map_tag_operating_profit() -> None:
    assert map_tag("OperatingProfit") == "operating_profit_loss"


def test_map_tag_profit_loss_for_period() -> None:
    assert map_tag("ProfitLossForPeriod") == "profit_loss_after_tax"


def test_map_tag_current_assets() -> None:
    assert map_tag("CurrentAssets") == "current_assets"


def test_map_tag_fixed_assets() -> None:
    assert map_tag("FixedAssets") == "fixed_assets"


def test_map_tag_total_assets_less_current_liabilities() -> None:
    assert map_tag("TotalAssetsLessCurrentLiabilities") == "total_assets_less_current_liabilities"


def test_map_tag_creditors_due_within_one_year() -> None:
    assert map_tag("CreditorsAmountsFallingDueWithinOneYear") == "creditors_due_within_one_year"


def test_map_tag_creditors_due_after_one_year() -> None:
    assert map_tag("CreditorsAmountsFallingDueAfterMoreThanOneYear") == "creditors_due_after_one_year"


def test_map_tag_net_assets() -> None:
    assert map_tag("NetAssetsLiabilities") == "net_assets_liabilities"


def test_map_tag_cash() -> None:
    assert map_tag("CashAndCashEquivalents") == "cash_bank_on_hand"


def test_map_tag_employees() -> None:
    assert map_tag("AverageNumberEmployeesDuringPeriod") == "average_number_of_employees"


# ---------------------------------------------------------------------------
# map_tag — normalisation
# ---------------------------------------------------------------------------


def test_map_tag_lowercases_input() -> None:
    assert map_tag("TURNOVER") == "revenue"
    assert map_tag("turnover") == "revenue"
    assert map_tag("Turnover") == "revenue"


def test_map_tag_strips_underscores() -> None:
    # Some taxonomies use underscored forms in tag names
    assert map_tag("Gross_Profit") == "gross_profit"


def test_map_tag_strips_hyphens() -> None:
    assert map_tag("Gross-Profit") == "gross_profit"


def test_map_tag_shareholders_funds() -> None:
    assert map_tag("ShareholdersFunds") == "net_assets_liabilities"


def test_map_tag_unknown_returns_none() -> None:
    assert map_tag("SomeObscureTagName") is None


def test_map_tag_empty_returns_none() -> None:
    assert map_tag("") is None


# ---------------------------------------------------------------------------
# map_label — direct lookups
# ---------------------------------------------------------------------------


def test_map_label_turnover() -> None:
    assert map_label("Turnover") == "revenue"


def test_map_label_gross_profit() -> None:
    assert map_label("Gross profit") == "gross_profit"


def test_map_label_operating_profit() -> None:
    assert map_label("Operating profit") == "operating_profit_loss"


def test_map_label_profit_after_tax() -> None:
    assert map_label("Profit after tax") == "profit_loss_after_tax"


def test_map_label_current_assets() -> None:
    assert map_label("Current assets") == "current_assets"


def test_map_label_fixed_assets() -> None:
    assert map_label("Fixed assets") == "fixed_assets"


def test_map_label_total_assets_less_current_liabilities() -> None:
    assert map_label("Total assets less current liabilities") == "total_assets_less_current_liabilities"


def test_map_label_creditors_within_one_year() -> None:
    assert map_label("Creditors due within one year") == "creditors_due_within_one_year"


def test_map_label_creditors_after_one_year() -> None:
    assert map_label("Creditors due after one year") == "creditors_due_after_one_year"


def test_map_label_net_assets() -> None:
    assert map_label("Net assets") == "net_assets_liabilities"


def test_map_label_cash_at_bank() -> None:
    assert map_label("Cash at bank and in hand") == "cash_bank_on_hand"


def test_map_label_employees() -> None:
    assert map_label("Average number of employees") == "average_number_of_employees"


# ---------------------------------------------------------------------------
# map_label — normalisation
# ---------------------------------------------------------------------------


def test_map_label_case_insensitive() -> None:
    assert map_label("TURNOVER") == "revenue"
    assert map_label("turnover") == "revenue"


def test_map_label_strips_leading_trailing_whitespace() -> None:
    assert map_label("  Turnover  ") == "revenue"


def test_map_label_collapses_internal_whitespace() -> None:
    assert map_label("Gross  profit") == "gross_profit"


def test_map_label_unknown_returns_none() -> None:
    assert map_label("Some random label") is None


def test_map_label_empty_returns_none() -> None:
    assert map_label("") is None


# ---------------------------------------------------------------------------
# All 12 canonical names are reachable
# ---------------------------------------------------------------------------


def test_all_canonical_names_reachable_via_tag() -> None:
    """Every canonical name can be reached via at least one tag mapping."""
    reached = set()
    tag_samples = {
        "revenue": "Turnover",
        "gross_profit": "GrossProfit",
        "operating_profit_loss": "OperatingProfit",
        "profit_loss_after_tax": "ProfitLossForPeriod",
        "current_assets": "CurrentAssets",
        "fixed_assets": "FixedAssets",
        "total_assets_less_current_liabilities": "TotalAssetsLessCurrentLiabilities",
        "creditors_due_within_one_year": "CreditorsAmountsFallingDueWithinOneYear",
        "creditors_due_after_one_year": "CreditorsAmountsFallingDueAfterMoreThanOneYear",
        "net_assets_liabilities": "NetAssetsLiabilities",
        "cash_bank_on_hand": "CashAndCashEquivalents",
        "average_number_of_employees": "AverageNumberEmployeesDuringPeriod",
    }
    for expected, tag in tag_samples.items():
        result = map_tag(tag)
        assert result == expected, f"Expected {expected} for tag {tag!r}, got {result!r}"
        reached.add(result)
    assert reached == ALL_CANONICAL


def test_all_canonical_names_reachable_via_label() -> None:
    """Every canonical name can be reached via at least one label mapping."""
    reached = set()
    label_samples = {
        "revenue": "Turnover",
        "gross_profit": "Gross profit",
        "operating_profit_loss": "Operating profit",
        "profit_loss_after_tax": "Profit after tax",
        "current_assets": "Current assets",
        "fixed_assets": "Fixed assets",
        "total_assets_less_current_liabilities": "Total assets less current liabilities",
        "creditors_due_within_one_year": "Creditors due within one year",
        "creditors_due_after_one_year": "Creditors due after one year",
        "net_assets_liabilities": "Net assets",
        "cash_bank_on_hand": "Cash at bank and in hand",
        "average_number_of_employees": "Average number of employees",
    }
    for expected, label in label_samples.items():
        result = map_label(label)
        assert result == expected, f"Expected {expected} for label {label!r}, got {result!r}"
        reached.add(result)
    assert reached == ALL_CANONICAL
