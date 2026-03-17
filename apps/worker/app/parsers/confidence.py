"""
Confidence scoring for extracted financial facts.

All scores are Decimal in [0.0, 1.0].

Score bands (docs/05-parser-design.md §Confidence scoring):
    high        >= 0.85
    medium      >= 0.65
    low         >= 0.40
    unavailable  < 0.40

Phase 5B scoring model:
    iXBRL path — relies on explicit tagged facts; highest confidence.
    HTML path  — semi-structured; label matching is heuristic.

These functions are intentionally simple and explicit.  The inputs are
boolean flags so tests can enumerate all combinations easily.  Phase 5C
can extend the model with additional dimensions (unit confidence,
validation penalties, etc.) without breaking existing callers.
"""

from __future__ import annotations

from decimal import Decimal


# ---------------------------------------------------------------------------
# Per-fact scoring
# ---------------------------------------------------------------------------


def score_ixbrl_fact(
    has_tag_mapping: bool,
    period_complete: bool,
    decimals_present: bool,
) -> Decimal:
    """
    Score a single fact extracted from an iXBRL document.

    Args:
        has_tag_mapping:  The XBRL tag resolved to a canonical fact name.
        period_complete:  The context has usable period dates (duration or
                         instant — either is acceptable).
        decimals_present: The ix:nonFraction element has a decimals attribute,
                         indicating the reporting precision was declared.

    Returns:
        Confidence score in [0.10, 0.95].
    """
    if has_tag_mapping:
        base = Decimal("0.95")
        if not period_complete:
            base -= Decimal("0.15")
        if not decimals_present:
            base -= Decimal("0.05")
    else:
        # Unmapped tags are not persisted, but we still score them for
        # diagnostic purposes (run_confidence includes all facts).
        base = Decimal("0.50")
        if not period_complete:
            base -= Decimal("0.10")

    return max(base, Decimal("0.10"))


def score_html_fact(
    has_label_mapping: bool,
    period_complete: bool,
    value_unambiguous: bool,
) -> Decimal:
    """
    Score a single fact extracted from an HTML semi-structured document.

    Args:
        has_label_mapping: The label resolved to a canonical fact name.
        period_complete:   Period dates were detected from the document.
                          (In Phase 5B, HTML period detection is not
                          implemented, so this will always be False.)
        value_unambiguous: The numeric value parsed without bracket or
                          sign ambiguity.

    Returns:
        Confidence score in [0.10, 0.75].
    """
    if has_label_mapping:
        base = Decimal("0.75")
        if not period_complete:
            base -= Decimal("0.10")
        if not value_unambiguous:
            base -= Decimal("0.10")
    else:
        base = Decimal("0.30")

    return max(base, Decimal("0.10"))


# ---------------------------------------------------------------------------
# Run-level aggregate
# ---------------------------------------------------------------------------


def aggregate_run_confidence(facts: list) -> Decimal:
    """
    Compute the aggregate confidence for an extraction run.

    Takes the mean confidence of all canonically-mapped facts.
    Returns 0.0 if no canonical facts were extracted.

    Args:
        facts: list of RawFact instances (from parsers.models).
    """
    mapped = [f for f in facts if f.canonical_name is not None]
    if not mapped:
        return Decimal("0")
    total = sum(f.extraction_confidence for f in mapped)
    return total / Decimal(len(mapped))


# ---------------------------------------------------------------------------
# Band classification (for display / signal generation)
# ---------------------------------------------------------------------------


def confidence_band(score: Decimal) -> str:
    """
    Map a confidence score to its human-readable band name.

    Returns one of: 'high', 'medium', 'low', 'unavailable'.
    """
    if score >= Decimal("0.85"):
        return "high"
    if score >= Decimal("0.65"):
        return "medium"
    if score >= Decimal("0.40"):
        return "low"
    return "unavailable"
