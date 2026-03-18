"""
HTML semi-structured extraction for Companies House account filings.

Entry point:
    extract_html(content: bytes) -> ExtractionResult

This is the fallback extraction path for documents that could not be
obtained as iXBRL.  HTML accounts from Companies House are typically
untagged profit-and-loss and balance-sheet tables.

Strategy:
1. Parse the document with lxml.html (forgiving HTML5 parser).
2. Detect the period end date from headings and title (Phase 5C).
3. Find all <table> elements that contain currency indicators.
4. For each qualifying table, detect the scale multiplier from headers
   (e.g. "£'000" → ×1000).
5. For each data row, try to match the first cell's label text against
   the canonical label synonym map.
6. Extract the first parseable numeric value (primary) and, if present,
   the second numeric value (comparative) from the remaining cells.
7. Assign confidence using html scoring formulas.

Known limitations (Phase 5C):
    - Period date detection uses regex on heading text; numeric date
      formats ("31/03/2023") and abbreviated months ("31 Mar 23") are
      not matched.
    - Comparative facts always have period_end=None; the prior year date
      cannot be reliably determined from HTML alone.
    - Multi-row headers and merged cells are not handled.
    - The same concept appearing in multiple tables may be captured twice;
      the task-level upsert ensures only one value is persisted per
      canonical name per period.
    - accounts_type is not detected from HTML in Phase 5C.
"""

from __future__ import annotations

import logging
import re
from datetime import date
from decimal import Decimal, InvalidOperation

from lxml import html as lhtml

from app.parsers.canonical_mapper import map_label
from app.parsers.confidence import aggregate_run_confidence, score_html_fact
from app.parsers.models import ExtractionResult, RawFact

log = logging.getLogger(__name__)

# Currency indicators that signal a financial table.
_CURRENCY_SIGNALS = frozenset(["£", "€", "$", "gbp", "usd", "eur"])

# Scale patterns in column headers.  Maps header text fragment → multiplier.
_SCALE_PATTERNS: list[tuple[re.Pattern[str], int]] = [
    (re.compile(r"000,?000|\bm(?:illion)?s?\b", re.I), 1_000_000),
    (re.compile(r"'000|,000|thousand", re.I), 1_000),
]

# Period end date detection patterns.
# Matches: "year ended 31 December 2023", "period ended 31st March 2022",
#          "as at 31 December 2023"
_PERIOD_END_PATTERNS: list[re.Pattern[str]] = [
    re.compile(
        r"\b(?:year|period)\s+ended?\b"
        r".*?"
        r"(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(january|february|march|april|may|june|july|august"
        r"|september|october|november|december)\s+"
        r"(\d{4})\b",
        re.I | re.DOTALL,
    ),
    re.compile(
        r"\bas\s+at\b"
        r".*?"
        r"(\d{1,2})(?:st|nd|rd|th)?\s+"
        r"(january|february|march|april|may|june|july|august"
        r"|september|october|november|december)\s+"
        r"(\d{4})\b",
        re.I | re.DOTALL,
    ),
]

_MONTH_NAMES: dict[str, int] = {
    "january": 1, "february": 2, "march": 3, "april": 4,
    "may": 5, "june": 6, "july": 7, "august": 8,
    "september": 9, "october": 10, "november": 11, "december": 12,
}


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_html(content: bytes) -> ExtractionResult:
    """
    Extract canonical financial facts from an HTML filing document.

    Returns an ExtractionResult even on parse failure; check errors.
    """
    try:
        # Parse as UTF-8 by default; lxml's HTML parser defaults to Latin-1
        # for raw bytes when no charset meta is present, which misinterprets
        # multi-byte characters like £ and €.
        doc = lhtml.fromstring(content, parser=lhtml.HTMLParser(encoding="utf-8"))
    except Exception as exc:
        return ExtractionResult(
            facts=[],
            period_start=None,
            period_end=None,
            accounts_type=None,
            currency_code="GBP",
            run_confidence=Decimal("0"),
            warnings=[],
            errors=[f"HTML parse failed: {exc}"],
            extraction_method="html",
        )

    # Detect period end from document headings / title
    period_end = _detect_html_period(doc)

    facts: list[RawFact] = []
    warnings: list[str] = []

    for table in doc.iter("table"):
        table_facts = _extract_from_table(table, period_end=period_end)
        facts.extend(table_facts)

    run_conf = aggregate_run_confidence(facts)

    return ExtractionResult(
        facts=facts,
        period_start=None,  # period_start not inferrable from HTML alone
        period_end=period_end,
        accounts_type=None,  # HTML does not carry structured accounts_type
        currency_code="GBP",
        run_confidence=run_conf,
        warnings=warnings,
        errors=[],
        extraction_method="html",
    )


# ---------------------------------------------------------------------------
# Period date detection
# ---------------------------------------------------------------------------


def _detect_html_period(doc: lhtml.HtmlElement) -> date | None:
    """
    Detect the period end date from document headings and title.

    Scans title, h1–h4, and p elements for "year/period ended DD Month YYYY"
    or "as at DD Month YYYY" patterns.  Returns the first matched date or None.
    """
    _SCAN_TAGS = ("title", "h1", "h2", "h3", "h4", "p")
    for tag in _SCAN_TAGS:
        for elem in doc.iter(tag):
            text = (elem.text_content() or "").strip()
            if not text:
                continue
            d = _try_match_period_date(text)
            if d is not None:
                return d
    return None


def _try_match_period_date(text: str) -> date | None:
    """Try to extract a period end date from a text string."""
    for pattern in _PERIOD_END_PATTERNS:
        m = pattern.search(text)
        if m:
            day_str, month_name, year_str = m.group(1), m.group(2).lower(), m.group(3)
            month = _MONTH_NAMES.get(month_name)
            if month is None:
                continue
            try:
                return date(int(year_str), month, int(day_str))
            except ValueError:
                continue
    return None


# ---------------------------------------------------------------------------
# Table extraction
# ---------------------------------------------------------------------------


def _is_financial_table(table: lhtml.HtmlElement) -> bool:
    """Return True if the table appears to contain financial data."""
    text_lower = (table.text_content() or "").lower()
    return any(sig in text_lower for sig in _CURRENCY_SIGNALS)


def _detect_table_scale(table: lhtml.HtmlElement) -> int:
    """
    Detect the scale multiplier from table header cells.

    Returns 1000 if '000 is found, 1000000 if millions, else 1 (as-is).
    The scale here is the multiplier (not a power of 10) because HTML
    tables often display amounts already scaled.
    """
    header_text = ""
    for row in table.iter("tr"):
        cells = list(row.iter("th")) + list(row.iter("td"))
        for cell in cells:
            cell_text = cell.text_content() or ""
            header_text += " " + cell_text
        # Only check first two rows for scale indicators
        break

    for pattern, multiplier in _SCALE_PATTERNS:
        if pattern.search(header_text):
            return multiplier
    return 1


def _extract_from_table(
    table: lhtml.HtmlElement,
    period_end: date | None = None,
) -> list[RawFact]:
    """
    Extract RawFact instances from a single HTML table.

    Captures up to two numeric value columns per row: the first as the
    primary (current year) fact and the second as a comparative (prior year)
    fact with is_comparative=True.

    Only returns facts that matched a canonical label synonym.
    """
    if not _is_financial_table(table):
        return []

    scale = _detect_table_scale(table)
    facts: list[RawFact] = []
    seen_canonical: set[str] = set()

    for row in table.iter("tr"):
        cells = [c for c in row if c.tag in ("td", "th")]
        if len(cells) < 2:
            continue

        label_text = (cells[0].text_content() or "").strip()
        if not label_text:
            continue

        canonical = map_label(label_text)
        if canonical is None:
            continue

        # Avoid duplicate primary facts from the same table (e.g. sub-total rows)
        if canonical in seen_canonical:
            continue

        # Collect up to two parseable numeric values from non-label cells
        values: list[tuple[str, Decimal, bool]] = []  # (raw_text, value, ambiguous)
        for cell in cells[1:]:
            raw_text = (cell.text_content() or "").strip()
            if not raw_text:
                continue
            fact_value, ambiguous = _parse_html_numeric(raw_text, scale)
            if fact_value is None:
                continue
            values.append((raw_text, fact_value, ambiguous))
            if len(values) == 2:
                break

        if not values:
            continue

        unit = "count" if canonical == "average_number_of_employees" else "GBP"

        # Primary fact (current year)
        raw_primary, primary_value, primary_ambiguous = values[0]
        primary_confidence = score_html_fact(
            has_label_mapping=True,
            period_complete=period_end is not None,
            value_unambiguous=not primary_ambiguous,
        )
        facts.append(
            RawFact(
                raw_label=label_text,
                raw_tag=None,
                raw_context_ref=None,
                raw_value=raw_primary,
                fact_value=primary_value,
                unit=unit,
                period_start=None,
                period_end=period_end,
                is_comparative=False,
                scale=0,  # scale already applied during parse
                canonical_name=canonical,
                mapping_method="synonym_label",
                extraction_confidence=primary_confidence,
            )
        )
        seen_canonical.add(canonical)

        # Comparative fact (prior year) — period_end unknown for HTML comparatives
        if len(values) >= 2:
            raw_comp, comp_value, comp_ambiguous = values[1]
            comp_confidence = score_html_fact(
                has_label_mapping=True,
                period_complete=False,  # comparative period date unknown
                value_unambiguous=not comp_ambiguous,
            )
            facts.append(
                RawFact(
                    raw_label=label_text,
                    raw_tag=None,
                    raw_context_ref=None,
                    raw_value=raw_comp,
                    fact_value=comp_value,
                    unit=unit,
                    period_start=None,
                    period_end=None,  # prior period date not determinable from HTML
                    is_comparative=True,
                    scale=0,
                    canonical_name=canonical,
                    mapping_method="synonym_label",
                    extraction_confidence=comp_confidence,
                )
            )

    return facts


# ---------------------------------------------------------------------------
# Numeric value parsing for HTML
# ---------------------------------------------------------------------------


def _parse_html_numeric(text: str, scale: int) -> tuple[Decimal | None, bool]:
    """
    Parse a numeric value from an HTML table cell.

    Returns (value, ambiguous) where:
      - value is the parsed Decimal or None if not parseable
      - ambiguous is True when the sign was inferred from bracket notation
        (some renderers use brackets for negatives, others for emphasis)

    Scale (integer multiplier, not power of 10) is applied after parsing.
    """
    text = text.strip()
    if not text or text in ("-", "–", "—", "nil", "n/a", "n.a.", "*"):
        return None, False

    from_brackets = text.startswith("(") and text.endswith(")")
    if from_brackets:
        text = text[1:-1]

    # Remove currency symbols, commas, NBSP
    text = re.sub(r"[£€$,\xa0\u202f\s]", "", text)

    # Remove trailing/leading percent
    text = text.strip("%")

    if not text:
        return None, False

    try:
        value = Decimal(text)
    except InvalidOperation:
        return None, False

    if from_brackets:
        value = -value

    if scale != 1:
        value *= Decimal(scale)

    return value, from_brackets
