"""
HTML semi-structured extraction for Companies House account filings.

Entry point:
    extract_html(content: bytes) -> ExtractionResult

This is the fallback extraction path for documents that could not be
obtained as iXBRL.  HTML accounts from Companies House are typically
untagged profit-and-loss and balance-sheet tables.

Strategy:
1. Parse the document with lxml.html (forgiving HTML5 parser).
2. Find all <table> elements that contain currency indicators.
3. For each qualifying table, detect the scale multiplier from headers
   (e.g. "£'000" → ×1000).
4. For each data row, try to match the first cell's label text against
   the canonical label synonym map.
5. Extract the first parseable numeric value from the remaining cells.
6. Assign confidence using html scoring formulas.

Known limitations (Phase 5B):
    - Period dates are not detected from HTML; period_start and period_end
      are always None.  The calling task uses filing.action_date as fallback.
    - Only the first numeric value column per row is captured; comparative
      columns are not extracted from HTML in Phase 5B.
    - Multi-row headers and merged cells are not handled.
    - The same concept appearing in multiple tables may be captured twice;
      the task-level upsert ensures only one value is persisted per
      canonical name per period.
"""

from __future__ import annotations

import logging
import re
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
    (re.compile(r"000,?000|m(?:illion)?s?", re.I), 1_000_000),
    (re.compile(r"'000|,000|thousand", re.I), 1_000),
]


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def extract_html(content: bytes) -> ExtractionResult:
    """
    Extract canonical financial facts from an HTML filing document.

    Returns an ExtractionResult even on parse failure; check errors.
    """
    try:
        doc = lhtml.fromstring(content)
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

    facts: list[RawFact] = []
    warnings: list[str] = []

    for table in doc.iter("table"):
        table_facts = _extract_from_table(table)
        facts.extend(table_facts)

    run_conf = aggregate_run_confidence(facts)

    return ExtractionResult(
        facts=facts,
        period_start=None,   # HTML period detection not implemented in Phase 5B
        period_end=None,
        accounts_type=None,
        currency_code="GBP",
        run_confidence=run_conf,
        warnings=warnings,
        errors=[],
        extraction_method="html",
    )


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


def _extract_from_table(table: lhtml.HtmlElement) -> list[RawFact]:
    """
    Extract RawFact instances from a single HTML table.

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

        # Avoid duplicate facts from the same table (e.g. sub-total rows)
        if canonical in seen_canonical:
            continue

        # Try to extract a numeric value from the non-label cells
        for cell in cells[1:]:
            raw_text = (cell.text_content() or "").strip()
            if not raw_text:
                continue
            fact_value, ambiguous = _parse_html_numeric(raw_text, scale)
            if fact_value is None:
                continue

            unit = "count" if canonical == "average_number_of_employees" else "GBP"
            confidence = score_html_fact(
                has_label_mapping=True,
                period_complete=False,   # HTML period not detected in Phase 5B
                value_unambiguous=not ambiguous,
            )

            facts.append(
                RawFact(
                    raw_label=label_text,
                    raw_tag=None,
                    raw_context_ref=None,
                    raw_value=raw_text,
                    fact_value=fact_value,
                    unit=unit,
                    period_start=None,
                    period_end=None,
                    is_comparative=False,
                    scale=0,  # scale already applied during parse
                    canonical_name=canonical,
                    mapping_method="synonym_label",
                    extraction_confidence=confidence,
                )
            )
            seen_canonical.add(canonical)
            break  # take only the first parseable value per label row

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
