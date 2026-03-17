"""
iXBRL (Inline XBRL) extraction for Companies House account filings.

Entry point:
    extract_ixbrl(content: bytes) -> ExtractionResult

The extractor:
1. Parses the document as XML (with recover fallback for HTML entities).
2. Detects the iXBRL inline namespace in use.
3. Extracts all XBRL context definitions (period dates).
4. Extracts all XBRL unit definitions (currency codes).
5. Iterates ix:nonFraction elements to collect numeric monetary facts.
6. Maps each fact's XBRL tag to a canonical fact name.
7. Scores each fact's confidence.
8. Determines the primary period from context frequency.
9. Marks comparative-year facts.

Numeric value parsing:
    Handles: scale attribute (10^n multiplier), sign="-" attribute,
    bracket notation (1,234) for negatives, comma/NBSP thousands
    separators.  sign and brackets are XOR-combined so that sign="-"
    with brackets produces a positive (they cancel each other).

Known limitations (Phase 5B):
    - ix:nonNumeric elements (text facts like employee counts from some
      taxonomies) are not extracted; only ix:nonFraction is processed.
    - accounts_type is not detected from the document; always None.
    - Segment/dimension context filtering is not applied; all facts in
      the primary context are treated as top-level.
"""

from __future__ import annotations

import logging
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import etree

from app.parsers.canonical_mapper import map_tag
from app.parsers.confidence import aggregate_run_confidence, score_ixbrl_fact
from app.parsers.models import ExtractionResult, RawFact

log = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Namespace constants
# ---------------------------------------------------------------------------

_XBRLI_NS = "http://www.xbrl.org/2003/instance"

# Multiple inline XBRL namespace versions appear in real UK filings.
_IX_NS_CANDIDATES = [
    "http://www.xbrl.org/2013/inlineXBRL",
    "http://xbrl.org/2013/inlineXBRL",
    "http://www.xbrl.org/2011/inlineXBRL",
]


# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _ContextInfo:
    period_start: date | None
    period_end: date | None
    is_instant: bool  # True = balance-sheet instant; False = duration period


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_ixbrl(content: bytes) -> ExtractionResult:
    """
    Extract canonical financial facts from an iXBRL document.

    Returns an ExtractionResult even on parse failure; check
    result.errors to determine whether extraction succeeded.
    """
    try:
        root = etree.fromstring(content)
    except etree.XMLSyntaxError:
        # Try lenient recovery (handles stray HTML entities etc.)
        try:
            root = etree.fromstring(content, parser=etree.XMLParser(recover=True))
        except etree.XMLSyntaxError as exc:
            return ExtractionResult(
                facts=[],
                period_start=None,
                period_end=None,
                accounts_type=None,
                currency_code="GBP",
                run_confidence=Decimal("0"),
                warnings=[],
                errors=[f"XML parse failed: {exc}"],
                extraction_method="ixbrl",
            )

    ix_ns = _detect_ix_namespace(root)
    if ix_ns is None:
        return ExtractionResult(
            facts=[],
            period_start=None,
            period_end=None,
            accounts_type=None,
            currency_code="GBP",
            run_confidence=Decimal("0"),
            warnings=["No iXBRL namespace detected in document"],
            errors=[],
            extraction_method="ixbrl",
        )

    contexts = _extract_contexts(root)
    units = _extract_units(root)
    facts = _extract_facts(root, ix_ns, contexts, units)

    period_start, period_end = _determine_primary_period(facts)

    # Mark facts that belong to a period other than the primary as comparative
    for fact in facts:
        if (
            fact.period_end is not None
            and period_end is not None
            and fact.period_end != period_end
        ):
            fact.is_comparative = True

    currency = _detect_currency(units)
    run_conf = aggregate_run_confidence(facts)

    return ExtractionResult(
        facts=facts,
        period_start=period_start,
        period_end=period_end,
        accounts_type=None,  # detected in Phase 5C
        currency_code=currency,
        run_confidence=run_conf,
        warnings=[],
        errors=[],
        extraction_method="ixbrl",
    )


# ---------------------------------------------------------------------------
# Namespace detection
# ---------------------------------------------------------------------------


def _detect_ix_namespace(root: etree._Element) -> str | None:
    """Return the iXBRL inline namespace URI used in this document, or None."""
    for ns in _IX_NS_CANDIDATES:
        tag = f"{{{ns}}}nonFraction"
        if next(root.iter(tag), None) is not None:
            return ns
        # Also check for the header element as confirmation
        tag_hdr = f"{{{ns}}}header"
        if next(root.iter(tag_hdr), None) is not None:
            return ns
    return None


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


def _extract_contexts(root: etree._Element) -> dict[str, _ContextInfo]:
    """
    Build a map of context_id → _ContextInfo from xbrli:context elements.

    Handles both duration (startDate/endDate) and instant contexts.
    """
    contexts: dict[str, _ContextInfo] = {}
    for ctx in root.iter(f"{{{_XBRLI_NS}}}context"):
        ctx_id = ctx.get("id")
        if not ctx_id:
            continue
        period = ctx.find(f"{{{_XBRLI_NS}}}period")
        if period is None:
            continue

        start_elem = period.find(f"{{{_XBRLI_NS}}}startDate")
        end_elem = period.find(f"{{{_XBRLI_NS}}}endDate")
        instant_elem = period.find(f"{{{_XBRLI_NS}}}instant")

        if start_elem is not None and end_elem is not None:
            try:
                ps = date.fromisoformat(start_elem.text.strip())
                pe = date.fromisoformat(end_elem.text.strip())
                contexts[ctx_id] = _ContextInfo(ps, pe, False)
            except (ValueError, AttributeError):
                pass
        elif instant_elem is not None:
            try:
                instant = date.fromisoformat(instant_elem.text.strip())
                contexts[ctx_id] = _ContextInfo(None, instant, True)
            except (ValueError, AttributeError):
                pass

    return contexts


# ---------------------------------------------------------------------------
# Unit extraction
# ---------------------------------------------------------------------------


def _extract_units(root: etree._Element) -> dict[str, str]:
    """
    Build a map of unit_id → currency code (or 'count' for pure/shares).
    """
    units: dict[str, str] = {}
    for unit_elem in root.iter(f"{{{_XBRLI_NS}}}unit"):
        unit_id = unit_elem.get("id")
        if not unit_id:
            continue
        measure = unit_elem.find(f"{{{_XBRLI_NS}}}measure")
        if measure is not None and measure.text:
            raw = measure.text.strip()
            # "iso4217:GBP" → "GBP", "xbrli:pure" → "count"
            local = raw.split(":", 1)[-1]
            if local.lower() in ("pure", "shares", "number"):
                units[unit_id] = "count"
            else:
                units[unit_id] = local.upper()
        else:
            units[unit_id] = "GBP"
    return units


# ---------------------------------------------------------------------------
# Fact extraction
# ---------------------------------------------------------------------------


def _extract_facts(
    root: etree._Element,
    ix_ns: str,
    contexts: dict[str, _ContextInfo],
    units: dict[str, str],
) -> list[RawFact]:
    """Iterate all ix:nonFraction elements and build RawFact instances."""
    facts: list[RawFact] = []
    for elem in root.iter(f"{{{ix_ns}}}nonFraction"):
        fact = _parse_nonfraction(elem, contexts, units)
        if fact is not None:
            facts.append(fact)
    return facts


def _parse_nonfraction(
    elem: etree._Element,
    contexts: dict[str, _ContextInfo],
    units: dict[str, str],
) -> RawFact | None:
    """Parse one ix:nonFraction element into a RawFact, or None on failure."""
    tag_name = elem.get("name", "")
    if not tag_name:
        return None

    context_ref = elem.get("contextRef", "")
    unit_ref = elem.get("unitRef", "")
    ctx = contexts.get(context_ref)
    unit = units.get(unit_ref, "GBP")

    # Collect all text content including from nested child elements
    raw_text = "".join(elem.itertext()).strip()
    if not raw_text:
        return None

    fact_value = _parse_numeric_value(
        raw_text,
        sign=elem.get("sign", ""),
        scale_str=elem.get("scale", "0"),
    )

    period_start = ctx.period_start if ctx else None
    period_end = ctx.period_end if ctx else None
    period_complete = ctx is not None  # True = we have some period info

    scale_str = elem.get("scale", "0")
    try:
        scale = int(scale_str)
    except ValueError:
        scale = 0

    # Strip namespace prefix for tag lookup: "uk-gaap:Turnover" → "Turnover"
    local_name = tag_name.split(":")[-1] if ":" in tag_name else tag_name
    canonical = map_tag(local_name)

    confidence = score_ixbrl_fact(
        has_tag_mapping=canonical is not None,
        period_complete=period_complete,
        decimals_present=elem.get("decimals") is not None,
    )

    return RawFact(
        raw_label=tag_name,
        raw_tag=tag_name,
        raw_context_ref=context_ref,
        raw_value=raw_text,
        fact_value=fact_value,
        unit=unit,
        period_start=period_start,
        period_end=period_end,
        is_comparative=False,  # set later by caller
        scale=scale,
        canonical_name=canonical,
        mapping_method="direct_tag" if canonical else None,
        extraction_confidence=confidence,
    )


# ---------------------------------------------------------------------------
# Numeric value parsing
# ---------------------------------------------------------------------------


def _parse_numeric_value(text: str, sign: str, scale_str: str) -> Decimal | None:
    """
    Parse an iXBRL numeric value string.

    Handles:
      - Bracket notation:  (1,234) → negative
      - sign="-" attribute:  negates the value
      - sign XOR brackets:  if both present, they cancel (XBRL convention)
      - scale attribute:  multiply by 10^scale
      - Comma / NBSP thousands separators
    """
    text = text.strip()
    if not text:
        return None

    from_brackets = text.startswith("(") and text.endswith(")")
    if from_brackets:
        text = text[1:-1]

    # Remove thousands separators and non-breaking spaces
    text = (
        text.replace(",", "")
        .replace("\xa0", "")
        .replace(" ", "")
        .replace("\u202f", "")
    )

    # Handle dash/nil values
    if text in ("-", "–", "—", "nil", ""):
        return None

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None

    # sign XOR brackets: both present → positive; one present → negative
    should_negate = (sign == "-") ^ from_brackets
    if should_negate:
        value = -value

    # Apply scale
    try:
        scale = int(scale_str)
    except ValueError:
        scale = 0
    if scale:
        value *= Decimal(10) ** scale

    return value


# ---------------------------------------------------------------------------
# Primary period detection
# ---------------------------------------------------------------------------


def _determine_primary_period(
    facts: list[RawFact],
) -> tuple[date | None, date | None]:
    """
    Identify the primary (current year) period from extracted facts.

    Strategy: the period_end referenced by the most facts is the primary
    period.  If there is a tie, the most recent date wins (favours
    current year over comparative).

    Returns (period_start, period_end) for the primary period.
    period_start may be None (e.g. from instant-only contexts).
    """
    period_end_counts: Counter[date] = Counter()
    for fact in facts:
        if fact.period_end is not None:
            period_end_counts[fact.period_end] += 1

    if not period_end_counts:
        return None, None

    primary_end = max(
        period_end_counts,
        key=lambda d: (period_end_counts[d], d),
    )

    # Find the corresponding period_start (from the first duration fact)
    for fact in facts:
        if fact.period_end == primary_end and fact.period_start is not None:
            return fact.period_start, primary_end

    return None, primary_end


# ---------------------------------------------------------------------------
# Currency detection
# ---------------------------------------------------------------------------


def _detect_currency(units: dict[str, str]) -> str:
    """
    Return the document currency.  Defaults to 'GBP' if not determinable.
    """
    for unit_code in units.values():
        if unit_code != "count" and len(unit_code) == 3:
            return unit_code
    return "GBP"
