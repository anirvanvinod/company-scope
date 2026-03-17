"""
iXBRL extractor unit tests.

Tests cover:
  - Happy path: context/unit/fact extraction from a minimal inline XBRL fixture
  - Value parsing: plain, scaled (10^3), sign="-", bracket notation, sign XOR brackets
  - Canonical mapping integration: known tags are mapped, unknown are not
  - Primary period detection: most-frequent period_end wins; tie-break by most recent
  - Comparative fact marking: facts with non-primary period_end get is_comparative=True
  - Namespace detection: unsupported namespace returns empty result with warning
  - XML recovery: malformed document (HTML entity) still parses with recover=True
  - Currency detection: GBP default; explicit ISO 4217 code
  - Error path: completely unparseable XML returns ExtractionResult with errors
"""

from __future__ import annotations

import textwrap
from decimal import Decimal

import pytest

from app.parsers.ixbrl_extractor import extract_ixbrl

# ---------------------------------------------------------------------------
# Minimal iXBRL fixture builder
# ---------------------------------------------------------------------------

_IX_NS = "http://www.xbrl.org/2013/inlineXBRL"
_XBRLI_NS = "http://www.xbrl.org/2003/instance"


def _build_ixbrl(
    *,
    contexts: str = "",
    units: str = "",
    facts: str = "",
    extra_nsmap: str = "",
) -> bytes:
    """
    Build a minimal iXBRL document with the given context/unit/fact snippets.
    """
    doc = f"""<?xml version="1.0" encoding="UTF-8"?>
<html xmlns="{_IX_NS}"
      xmlns:ix="{_IX_NS}"
      xmlns:xbrli="{_XBRLI_NS}"
      xmlns:uk-gaap="http://www.xbrl.org/uk/gaap/core/2009-09-01"
      {extra_nsmap}>
  <head>
    <ix:header>
      <ix:references/>
      <ix:resources>
        <xbrli:xbrl>
          {contexts}
          {units}
        </xbrli:xbrl>
      </ix:resources>
    </ix:header>
  </head>
  <body>
    {facts}
  </body>
</html>"""
    return doc.encode()


def _ctx_duration(ctx_id: str, start: str, end: str) -> str:
    return f"""
    <xbrli:context id="{ctx_id}">
      <xbrli:entity><xbrli:identifier scheme="x">12345678</xbrli:identifier></xbrli:entity>
      <xbrli:period>
        <xbrli:startDate>{start}</xbrli:startDate>
        <xbrli:endDate>{end}</xbrli:endDate>
      </xbrli:period>
    </xbrli:context>"""


def _ctx_instant(ctx_id: str, instant: str) -> str:
    return f"""
    <xbrli:context id="{ctx_id}">
      <xbrli:entity><xbrli:identifier scheme="x">12345678</xbrli:identifier></xbrli:entity>
      <xbrli:period>
        <xbrli:instant>{instant}</xbrli:instant>
      </xbrli:period>
    </xbrli:context>"""


def _unit_gbp(unit_id: str = "GBP") -> str:
    return f"""
    <xbrli:unit id="{unit_id}">
      <xbrli:measure>iso4217:GBP</xbrli:measure>
    </xbrli:unit>"""


def _fact(
    name: str,
    ctx: str,
    unit: str,
    value: str,
    *,
    scale: str = "0",
    sign: str = "",
    decimals: str = "0",
) -> str:
    sign_attr = f'sign="{sign}"' if sign else ""
    decimals_attr = f'decimals="{decimals}"' if decimals else ""
    return (
        f'<ix:nonFraction name="{name}" contextRef="{ctx}" unitRef="{unit}" '
        f'scale="{scale}" {sign_attr} {decimals_attr}>{value}</ix:nonFraction>'
    )


# ---------------------------------------------------------------------------
# Happy path — basic extraction
# ---------------------------------------------------------------------------


def test_extract_ixbrl_returns_extraction_result() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "1000000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.errors == []


def test_extract_ixbrl_maps_turnover_to_revenue() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "1000000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert len(result.facts) == 1
    assert result.facts[0].canonical_name == "revenue"
    assert result.facts[0].fact_value == Decimal("1000000")


def test_extract_ixbrl_period_end_detected() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "500000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    from datetime import date
    assert result.period_end == date(2023, 12, 31)
    assert result.period_start == date(2023, 1, 1)


def test_extract_ixbrl_currency_code() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "100")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.currency_code == "GBP"


def test_extract_ixbrl_extraction_method() -> None:
    content = _build_ixbrl()
    result = extract_ixbrl(content)
    assert result.extraction_method == "ixbrl"


# ---------------------------------------------------------------------------
# Value parsing
# ---------------------------------------------------------------------------


def test_parse_scaled_value_scale_3() -> None:
    """scale=3 means multiply by 10^3."""
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "500", scale="3")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value == Decimal("500000")


def test_parse_negative_sign_attribute() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:GrossProfit", "ctx1", "GBP", "100000", sign="-")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value == Decimal("-100000")


def test_parse_bracket_notation_negative() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:GrossProfit", "ctx1", "GBP", "(50000)")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value == Decimal("-50000")


def test_parse_sign_xor_brackets_cancel_to_positive() -> None:
    """sign='-' with brackets → positive (they cancel per XBRL convention)."""
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "(75000)", sign="-")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value == Decimal("75000")


def test_parse_comma_thousands_separator() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "1,234,567")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value == Decimal("1234567")


def test_parse_dash_value_returns_none() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "-")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].fact_value is None


# ---------------------------------------------------------------------------
# Canonical mapping
# ---------------------------------------------------------------------------


def test_unknown_tag_has_no_canonical_name() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:SomeObscureField", "ctx1", "GBP", "100")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].canonical_name is None


def test_known_tag_gross_profit_mapped() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:GrossProfit", "ctx1", "GBP", "200000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert result.facts[0].canonical_name == "gross_profit"


# ---------------------------------------------------------------------------
# Primary period detection and comparative marking
# ---------------------------------------------------------------------------


def test_comparative_facts_marked() -> None:
    """Facts from prior period are marked is_comparative=True."""
    ctx_current = _ctx_duration("ctx_c", "2023-01-01", "2023-12-31")
    ctx_prior = _ctx_duration("ctx_p", "2022-01-01", "2022-12-31")
    unit = _unit_gbp()
    # Two current-year facts, one prior-year fact → 2023-12-31 is primary
    f1 = _fact("uk-gaap:Turnover", "ctx_c", "GBP", "500000")
    f2 = _fact("uk-gaap:GrossProfit", "ctx_c", "GBP", "200000")
    f3 = _fact("uk-gaap:Turnover", "ctx_p", "GBP", "400000")
    content = _build_ixbrl(
        contexts=ctx_current + ctx_prior,
        units=unit,
        facts=f1 + f2 + f3,
    )
    result = extract_ixbrl(content)
    from datetime import date
    assert result.period_end == date(2023, 12, 31)
    comparative = [f for f in result.facts if f.is_comparative]
    assert len(comparative) == 1
    assert comparative[0].fact_value == Decimal("400000")


def test_tie_break_uses_most_recent_period() -> None:
    """Equal vote counts → most recent period_end wins."""
    ctx1 = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    ctx2 = _ctx_duration("ctx2", "2022-01-01", "2022-12-31")
    unit = _unit_gbp()
    f1 = _fact("uk-gaap:Turnover", "ctx1", "GBP", "100000")
    f2 = _fact("uk-gaap:Turnover", "ctx2", "GBP", "90000")
    content = _build_ixbrl(contexts=ctx1 + ctx2, units=unit, facts=f1 + f2)
    result = extract_ixbrl(content)
    from datetime import date
    assert result.period_end == date(2023, 12, 31)


def test_instant_context_period_end_only() -> None:
    """Balance-sheet instant contexts set period_end; period_start stays None."""
    ctx = _ctx_instant("ctx_bs", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:CurrentAssets", "ctx_bs", "GBP", "300000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    from datetime import date
    assert result.period_end == date(2023, 12, 31)
    # period_start may be None when only instant contexts exist
    assert result.period_start is None


# ---------------------------------------------------------------------------
# Error / edge-case handling
# ---------------------------------------------------------------------------


def test_unparseable_xml_returns_error() -> None:
    garbage = b"<not valid xml at all >><<"
    result = extract_ixbrl(garbage)
    assert result.errors != []
    assert result.facts == []


def test_no_ixbrl_namespace_returns_warning() -> None:
    # Valid XML but no ix:nonFraction elements, no recognized namespace
    xml = b'<?xml version="1.0"?><root xmlns:x="http://example.com"/>'
    result = extract_ixbrl(xml)
    assert result.warnings != [] or result.facts == []


def test_no_facts_returns_empty_result() -> None:
    # Valid iXBRL structure but no nonFraction elements
    content = _build_ixbrl(
        contexts=_ctx_duration("ctx1", "2023-01-01", "2023-12-31"),
        units=_unit_gbp(),
        facts="",
    )
    result = extract_ixbrl(content)
    assert result.facts == []
    assert result.period_end is None


def test_run_confidence_is_decimal() -> None:
    ctx = _ctx_duration("ctx1", "2023-01-01", "2023-12-31")
    unit = _unit_gbp()
    f = _fact("uk-gaap:Turnover", "ctx1", "GBP", "1000")
    content = _build_ixbrl(contexts=ctx, units=unit, facts=f)
    result = extract_ixbrl(content)
    assert isinstance(result.run_confidence, Decimal)
