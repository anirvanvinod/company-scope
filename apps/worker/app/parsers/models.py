"""
Data models for the parser pipeline.

RawFact       — a single extracted value before persistence
ExtractionResult — the complete output from one document extraction
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date
from decimal import Decimal


@dataclass
class RawFact:
    """
    A single financial fact as extracted from a document.

    Before persistence:
      - canonical_name is None if no mapping was found
      - fact_value is None if the numeric value could not be parsed
        (never store None as zero — preserve it as None)
      - is_comparative is True for prior-year comparative values

    After canonical mapping:
      - mapping_method identifies how the canonical name was resolved
        ('direct_tag' for XBRL, 'synonym_label' for HTML)
    """

    raw_label: str              # XBRL tag name or HTML label text
    raw_tag: str | None         # full XBRL tag (e.g. "uk-gaap:Turnover"); None for HTML
    raw_context_ref: str | None # XBRL context reference ID; None for HTML
    raw_value: str              # original text as it appeared in the document

    fact_value: Decimal | None  # parsed numeric value; None = not parseable
    unit: str                   # "GBP", "USD", or "count" for employees

    period_start: date | None   # None for instant contexts or undetected
    period_end: date | None     # None if period could not be determined

    is_comparative: bool        # True if this is a prior-year comparative

    scale: int                  # power-of-10 scale already applied (0 = as-is)
    canonical_name: str | None  # resolved canonical fact name; None = unmapped
    mapping_method: str | None  # "direct_tag" | "synonym_label" | None

    extraction_confidence: Decimal  # 0.0–1.0


@dataclass
class ExtractionResult:
    """
    Complete output from extracting one filing document.

    facts includes ALL extracted facts including unmapped ones.
    Only facts with canonical_name != None and fact_value != None
    are persisted to financial_facts.

    period_start / period_end are the primary period detected from the
    document itself (may be None for HTML documents).  The calling task
    uses the filing action_date as a fallback.
    """

    facts: list[RawFact]
    period_start: date | None   # primary period start
    period_end: date | None     # primary period end
    accounts_type: str | None   # e.g. "micro-entity", "small", "full"
    currency_code: str          # "GBP" by default
    run_confidence: Decimal     # mean confidence across canonical-mapped facts
    warnings: list[str]
    errors: list[str]
    extraction_method: str      # "ixbrl" or "html"
