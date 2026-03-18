"""
iXBRL (Inline XBRL) extraction for Companies House account filings.

Entry point:
    extract_ixbrl(content: bytes) -> ExtractionResult

The extractor:
1. Parses the document as XML (with recover fallback for HTML entities).
2. Detects the iXBRL inline namespace in use.
3. Extracts all XBRL context definitions (period dates, segment flags).
4. Extracts all XBRL unit definitions (currency codes).
5. Iterates ix:nonFraction and ix:nonNumeric elements to collect facts.
6. Maps each fact's XBRL tag to a canonical fact name.
7. Scores each fact's confidence.
8. Determines the primary period from context frequency.
9. Marks comparative-year facts.
10. Detects accounts_type from taxonomy tags or document headings.

Numeric value parsing:
    Handles: scale attribute (10^n multiplier), sign="-" attribute,
    bracket notation (1,234) for negatives, comma/NBSP thousands
    separators.  sign and brackets are XOR-combined so that sign="-"
    with brackets produces a positive (they cancel each other).

Segment filtering (Phase 5C):
    XBRL contexts containing xbrli:segment or xbrli:scenario elements
    indicate dimensional (non-consolidated) facts and are excluded from
    extraction.  Only top-level entity-wide contexts are retained.

Known limitations (Phase 5C):
    - ix:nonNumeric parsing attempts decimal extraction from text content;
      non-numeric text facts (e.g. company names) are silently skipped.
    - accounts_type detection from heading text may mis-fire if "dormant"
      or "small" appears in a company name or boilerplate text.
    - Segment filtering excludes all dimensioned contexts conservatively;
      rare edge cases where xbrli:segment is used for non-segment purposes
      will also be excluded.
"""

from __future__ import annotations

import logging
import re
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
# Accounts type detection
# ---------------------------------------------------------------------------

# XBRL local tag names (lowercased, no separators) that carry accounts type
_ACCOUNTS_TYPE_TAGS: frozenset[str] = frozenset([
    "accountstype",
    "typeofaccounts",
    "typeofreport",
])

# Normalise raw accounts type text → canonical value
_ACCOUNTS_TYPE_NORMALISE: dict[str, str] = {
    "micro": "micro-entity",
    "microentity": "micro-entity",
    "microentityaccounts": "micro-entity",
    "microentityreport": "micro-entity",
    "small": "small",
    "smallcompany": "small",
    "smallcompanyaccounts": "small",
    "full": "full",
    "fullaccounts": "full",
    "dormant": "dormant",
    "dormantcompany": "dormant",
    "dormantcompanyaccounts": "dormant",
    "abridged": "abridged",
    "abridgedaccounts": "abridged",
    "abbreviated": "abbreviated",
    "abbreviatedaccounts": "abbreviated",
}

# ---------------------------------------------------------------------------
# Internal data structures
# ---------------------------------------------------------------------------


@dataclass
class _ContextInfo:
    period_start: date | None
    period_end: date | None
    is_instant: bool  # True = balance-sheet instant; False = duration period
    is_segmented: bool = False  # True = has xbrli:segment or xbrli:scenario


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
    accounts_type = _detect_accounts_type(root, ix_ns)

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
        accounts_type=accounts_type,
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
        if (
            next(root.iter(f"{{{ns}}}nonFraction"), None) is not None
            or next(root.iter(f"{{{ns}}}nonNumeric"), None) is not None
            or next(root.iter(f"{{{ns}}}header"), None) is not None
        ):
            return ns
    return None


# ---------------------------------------------------------------------------
# Context extraction
# ---------------------------------------------------------------------------


def _extract_contexts(root: etree._Element) -> dict[str, _ContextInfo]:
    """
    Build a map of context_id → _ContextInfo from xbrli:context elements.

    Handles both duration (startDate/endDate) and instant contexts.
    Contexts with xbrli:segment or xbrli:scenario descendants are flagged as
    segmented (dimensional); their facts are excluded from extraction.
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

        # Detect dimensional contexts (non-consolidated segment/scenario facts)
        has_segment = ctx.find(f".//{{{_XBRLI_NS}}}segment") is not None
        has_scenario = ctx.find(f".//{{{_XBRLI_NS}}}scenario") is not None
        is_segmented = has_segment or has_scenario

        if start_elem is not None and end_elem is not None:
            try:
                ps = date.fromisoformat(start_elem.text.strip())
                pe = date.fromisoformat(end_elem.text.strip())
                contexts[ctx_id] = _ContextInfo(ps, pe, False, is_segmented)
            except (ValueError, AttributeError):
                pass
        elif instant_elem is not None:
            try:
                instant = date.fromisoformat(instant_elem.text.strip())
                contexts[ctx_id] = _ContextInfo(None, instant, True, is_segmented)
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
    """
    Iterate ix:nonFraction and ix:nonNumeric elements and build RawFact instances.

    Segmented contexts (with xbrli:segment or xbrli:scenario) are skipped so
    that only top-level, entity-wide facts are extracted.
    """
    facts: list[RawFact] = []

    # nonFraction: numeric monetary / ratio facts
    for elem in root.iter(f"{{{ix_ns}}}nonFraction"):
        fact = _parse_nonfraction(elem, contexts, units)
        if fact is not None:
            facts.append(fact)

    # nonNumeric: text-valued facts (e.g. employee counts in some UK taxonomies)
    for elem in root.iter(f"{{{ix_ns}}}nonNumeric"):
        fact = _parse_nonnumeric(elem, contexts)
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

    # Skip facts in segmented (dimensional) contexts
    if ctx is not None and ctx.is_segmented:
        return None

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


def _parse_nonnumeric(
    elem: etree._Element,
    contexts: dict[str, _ContextInfo],
) -> RawFact | None:
    """
    Parse one ix:nonNumeric element into a RawFact if it yields a mappable
    numeric value (e.g. average employee counts tagged as text in some filings).

    Non-numeric text values (company names, addresses, narrative text) are
    silently skipped via the decimal parse guard in _parse_nonnumeric_value.
    """
    tag_name = elem.get("name", "")
    if not tag_name:
        return None

    # Only process tags we can map to a canonical name
    local_name = tag_name.split(":")[-1] if ":" in tag_name else tag_name
    canonical = map_tag(local_name)
    if canonical is None:
        return None

    context_ref = elem.get("contextRef", "")
    ctx = contexts.get(context_ref)

    # Skip segmented (dimensional) contexts
    if ctx is not None and ctx.is_segmented:
        return None

    raw_text = "".join(elem.itertext()).strip()
    if not raw_text:
        return None

    fact_value = _parse_nonnumeric_value(raw_text)
    if fact_value is None:
        return None

    period_start = ctx.period_start if ctx else None
    period_end = ctx.period_end if ctx else None
    period_complete = ctx is not None

    confidence = score_ixbrl_fact(
        has_tag_mapping=True,
        period_complete=period_complete,
        decimals_present=False,  # nonNumeric elements have no decimals attribute
    )

    return RawFact(
        raw_label=tag_name,
        raw_tag=tag_name,
        raw_context_ref=context_ref,
        raw_value=raw_text,
        fact_value=fact_value,
        unit="count",
        period_start=period_start,
        period_end=period_end,
        is_comparative=False,
        scale=0,
        canonical_name=canonical,
        mapping_method="direct_tag",
        extraction_confidence=confidence,
    )


def _parse_nonnumeric_value(text: str) -> Decimal | None:
    """
    Extract a numeric value from ix:nonNumeric text content.

    Handles plain integers ("25"), comma-separated numbers ("1,234"),
    and leading-digit extraction ("25 (2022: 23)").
    Returns None if no numeric value can be extracted.
    """
    text = text.strip()
    if not text:
        return None

    # Remove thousands separators and whitespace
    cleaned = text.replace(",", "").replace("\xa0", "").replace(" ", "")

    try:
        return Decimal(cleaned)
    except InvalidOperation:
        pass

    # Try to extract a leading integer (e.g. "25 employees", "25 (2022: 23)")
    match = re.match(r"^(\d+)", text)
    if match:
        try:
            return Decimal(match.group(1))
        except InvalidOperation:
            pass

    return None


# ---------------------------------------------------------------------------
# Accounts type detection
# ---------------------------------------------------------------------------


def _detect_accounts_type(root: etree._Element, ix_ns: str) -> str | None:
    """
    Detect accounts type from iXBRL taxonomy tags or document headings.

    Priority:
      1. ix:nonNumeric element with an AccountsType / TypeOfAccounts tag name.
      2. Document heading text (h1–h4, title) containing keywords.

    Returns a normalised accounts_type string ('micro-entity', 'small', 'full',
    'dormant', 'abridged', 'abbreviated') or None if not determinable.
    """
    # 1. Look for explicit taxonomy tag in nonNumeric elements
    for elem in root.iter(f"{{{ix_ns}}}nonNumeric"):
        tag_name = elem.get("name", "")
        local_norm = (
            tag_name.split(":")[-1] if ":" in tag_name else tag_name
        ).lower().replace("_", "").replace("-", "")
        if local_norm in _ACCOUNTS_TYPE_TAGS:
            text = "".join(elem.itertext()).strip()
            result = _normalise_accounts_type(text)
            if result:
                return result

    # 2. Fallback: scan document headings for keyword markers
    return _detect_accounts_type_from_text(root)


def _normalise_accounts_type(text: str) -> str | None:
    """Normalise raw accounts type text to a canonical value."""
    key = text.lower().replace(" ", "").replace("-", "").replace("_", "")
    return _ACCOUNTS_TYPE_NORMALISE.get(key)


def _detect_accounts_type_from_text(root: etree._Element) -> str | None:
    """
    Scan document heading elements for accounts type keywords.

    Iterates h1–h4 and title elements only; limits scan to avoid false
    positives from body text.
    """
    _HEADING_LOCAL_NAMES = frozenset(["h1", "h2", "h3", "h4", "title"])
    checked = 0
    for elem in root.iter():
        if not isinstance(elem.tag, str):
            continue
        local = elem.tag.rpartition("}")[2].lower()
        if local not in _HEADING_LOCAL_NAMES:
            continue
        text = " ".join(elem.itertext()).lower()
        if not text:
            continue
        if "micro-entity" in text or "micro entity" in text:
            return "micro-entity"
        if "dormant" in text:
            return "dormant"
        if "abridged" in text:
            return "abridged"
        if "abbreviated" in text:
            return "abbreviated"
        if "small company" in text or "small companies" in text:
            return "small"
        if "full accounts" in text:
            return "full"
        checked += 1
        if checked >= 20:
            break
    return None


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
