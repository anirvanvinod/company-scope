# Parser Design

## Purpose
The parser layer converts Companies House account-related filings and document representations into a structured, period-based financial dataset with confidence scoring and traceability.

This parser is not an accounting engine. It is a controlled extraction and normalisation pipeline designed to transform public filings into explainable facts suitable for downstream charts, metrics, and rule-based signals.

## Design goals
- Prefer official source documents over inferred values
- Preserve traceability from each extracted value to its source document and filing
- Handle multiple filing formats gracefully
- Store uncertainty explicitly
- Support re-parsing when parser logic improves
- Avoid silently converting missing data into zero values

## Key constraints
- Companies House data formats are inconsistent across companies and time periods
- Not every filing exposes clean machine-readable financial values
- The same concept may appear under different labels in different account types
- Micro-entity, small, abridged, dormant, and full accounts expose different levels of detail
- Restatements may change previously observed values

## Supported document and data sources

### Phase 1 sources
1. Filing history metadata from Companies House
2. Document API metadata and fetched document content
3. Structured representations when available:
   - iXBRL
   - XBRL
   - HTML representations with tagged or semi-structured data

### Phase 2 sources
1. Bulk accounts datasets
2. Historical backfills
3. Supplemental benchmark datasets

## Parser service boundaries

The parser service is responsible for:
- selecting relevant account filings
- fetching document metadata
- downloading document content
- detecting document format
- extracting line items
- mapping raw labels or tags to canonical fact names
- validating extracted values
- assigning confidence scores
- persisting structured facts

The parser service is not responsible for:
- UI rendering
- user-facing explanation copy
- business pricing logic
- final risk scoring presentation
- regulated financial interpretation

## End-to-end parser flow

1. Company ingestion identifies filing history items
2. Filing classifier marks account-related filings
3. Document resolver fetches document metadata
4. Document fetcher downloads content to object storage
5. Format detector identifies iXBRL, XBRL, HTML, or unsupported type
6. Extractor parses structured values
7. Canonical mapper aligns raw facts to standard internal names
8. Validator applies consistency checks
9. Confidence scorer assigns confidence per fact
10. Persistence layer writes financial periods, facts, and extraction runs
11. Downstream analytics service derives metrics and trends

## Filing classification

### Relevant filing categories
- annual accounts
- dormant accounts
- micro-entity accounts
- abridged accounts
- small company accounts
- full accounts
- amended or restated accounts

### Filing classifier output
Each filing should be labelled with:
- filing_id
- company_number
- filing_type
- filing_date
- is_accounts_filing
- expected_document_required
- likely_period_end
- parser_priority
- parser_status

## Document storage strategy

Store:
- raw document metadata
- original downloaded file or normalised representation
- extracted facts
- parser logs
- validation results

Recommended object storage layout:

```text
/companyscope-documents/
  /{company_number}/
    /{filing_id}/
      original.bin
      metadata.json
      extracted.json
      validation.json
      parser.log
```

## Format detection

### Supported formats
- iXBRL
- XBRL
- HTML
- plain text fallback
- unsupported binary or image-based document

### Detection approach
Use content-type metadata first, then inspect document content signatures.

### Detection rules
- XHTML with inline tags -> iXBRL likely
- XML with XBRL namespaces -> XBRL likely
- HTML tables without structured tags -> HTML semi-structured
- scanned PDF or image-only content -> unsupported for structured extraction in MVP

## Extraction strategy by format

### iXBRL / XBRL
Preferred path.

Use a proper XBRL-capable parser where possible. Extract:
- tagged facts
- contexts
- periods
- units
- decimals / scale information
- taxonomy labels

Advantages:
- highest confidence
- clearer period alignment
- better support for canonical mapping

### HTML semi-structured extraction
Fallback path.

Use:
- DOM parsing
- table detection
- heading analysis
- label-value matching
- numeric coercion with UK formatting rules

Risks:
- ambiguous labels
- context loss
- period misalignment
- hidden formatting quirks

### Unsupported documents
Mark as unsupported, preserve metadata, and surface low-confidence or unavailable state to downstream systems.

## Canonical fact schema

Store facts using internal canonical names.

### Example canonical facts
- revenue
- gross_profit
- operating_profit_loss
- profit_loss_after_tax
- current_assets
- fixed_assets
- total_assets_less_current_liabilities
- creditors_due_within_one_year
- creditors_due_after_one_year
- net_assets_liabilities
- cash_bank_on_hand
- average_number_of_employees

### Mapping layer
Each extracted raw value should preserve:
- raw_label
- raw_tag
- raw_context_ref
- canonical_name
- mapping_method
- mapping_version

### Mapping methods
- direct taxonomy mapping
- synonym label mapping
- rule-based structural mapping
- derived calculation

## Period handling

A core requirement is period-based storage.

### Rules
- Prefer explicit period end from structured context
- Associate each fact with period_start and period_end where possible
- If only end date is known, persist end date and null start date with reduced confidence
- Support restated prior-year comparative values separately
- Never overwrite prior facts without versioning or supersession logic

### Comparative columns
Where filings include current year and prior year:
- treat them as distinct facts
- preserve relation to same source document
- mark one as comparative if necessary

## Numeric normalisation

### Standardisation rules
- store monetary values as decimals
- store percentages separately
- preserve original currency when available
- default currency to GBP only when clearly implied and not contradicted
- preserve sign direction
- track scale multipliers such as thousands or millions

### Dangerous cases
- bracketed negatives
- en dash or unusual minus symbols
- merged cells creating label ambiguity
- numbers rounded to nearest thousand
- inconsistent decimal scale

## Validation rules

### Structural validation
- fact must have source_document_id
- fact must have company_number
- period end must be parsable if present
- unsupported units should be flagged

### Financial sanity checks
- cash should not exceed current assets by large unexplained margin
- current assets and creditors should not parse as text blobs
- comparative period should generally precede current period
- derived net assets should roughly align with extracted net assets when both exist

### Validation outcomes
- pass
- pass_with_warnings
- fail_non_blocking
- fail_blocking

## Confidence scoring

Each fact gets a score and explanation.

### Dimensions
- source_format_confidence
- extraction_confidence
- mapping_confidence
- period_confidence
- unit_confidence
- validation_penalty

### Example scoring model
- direct tagged iXBRL fact with matching taxonomy and clean period: 0.95 to 1.00
- HTML table with matched label and clear currency context: 0.70 to 0.85
- inferred value from nearby label pattern: 0.40 to 0.60
- ambiguous extraction or uncertain period: below 0.40

### Confidence band labels
- high
- medium
- low
- unavailable

## Re-parsing and versioning

Parser logic will improve over time.

### Requirements
- every extraction run must store parser_version
- facts must reference extraction_run_id
- re-parsing should not destroy history
- downstream aggregates should be rebuildable from raw facts

### Recommended tables
- parser_runs
- parser_run_events
- financial_facts
- financial_fact_supersessions

## Error handling

### Retryable failures
- Companies House transient errors
- document download timeout
- temporary parser service crash

### Non-retryable failures
- permanently unsupported format
- malformed content that cannot be parsed
- missing document location

### Logging
Log:
- filing_id
- document_id
- parser_version
- failure stage
- exception type
- human-readable summary

## Pseudocode flow

```python
def parse_accounts_filing(company_number: str, filing_id: str) -> ParseResult:
    filing = get_filing_metadata(company_number, filing_id)
    document = resolve_document(filing)
    raw_content = fetch_document(document)
    fmt = detect_format(raw_content, document.content_type)

    if fmt not in SUPPORTED_FORMATS:
        return mark_unsupported(filing, document, fmt)

    raw_facts = extract_raw_facts(raw_content, fmt)
    mapped_facts = map_to_canonical(raw_facts)
    validated_facts = validate_facts(mapped_facts)
    scored_facts = score_confidence(validated_facts, fmt)

    persist_parse_run(filing, document, scored_facts)
    return build_result(scored_facts)
```

## Recommended Python libraries
- pydantic
- lxml
- beautifulsoup4
- pandas
- python-dateutil
- decimal
- arelle for XBRL evaluation

## Interfaces

### Input
- company_number
- filing_id
- document metadata
- raw document content

### Output
- parse run summary
- extracted facts
- validation warnings
- confidence scores
- error classification

## MVP scope
Support:
- filing classification
- document fetching
- iXBRL and HTML extraction for common account cases
- confidence scoring
- period-based persistence
- re-parse support

Do not support initially:
- OCR-heavy pipelines
- image-based PDF accounting extraction
- full accounting statement reconstruction for every format variation
- advanced semantic inference over management commentary

## Success metrics
- percentage of account filings successfully classified
- percentage of supported documents parsed
- fact extraction coverage for target canonical fields
- confidence distribution by format
- parser rerun reproducibility
- downstream metric completeness

## Open issues
- exact XBRL taxonomy mapping coverage
- handling amended filings and supersessions
- deduplicating nearly identical restated facts
- strategy for scanned PDFs in future versions
