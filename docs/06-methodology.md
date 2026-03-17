# Methodology

## Purpose
This document explains how CompanyScope turns public Companies House data into company intelligence in a transparent and reproducible way.

The aim is to help users understand:
- what the platform shows
- where the information comes from
- how derived metrics are calculated
- how risk signals are generated
- what the limits of the analysis are

This product is designed for explainable due diligence and public-data interpretation. It is not investment advice, legal advice, accounting advice, or a substitute for professional credit assessment.

## Source hierarchy

### Primary sources
CompanyScope relies primarily on official public sources, especially:
- Companies House Public Data API
- Companies House Document API
- official company filings and accounts documents
- optional streaming updates from Companies House for watchlist freshness

### Secondary sources
Secondary sources may be added later for benchmarking or enrichment, but they must always be clearly marked as non-primary.

Examples:
- sector benchmarking datasets
- insolvency-related public datasets
- macroeconomic context datasets

## Source-first principle
Every displayed metric, statement, or signal should be classed as one of the following:

1. Raw official fact  
   A value or item taken directly from an official source.

2. Parsed structured fact  
   A value extracted from an official filing document and normalised into the platform’s schema.

3. Derived metric  
   A value calculated from one or more raw or parsed facts.

4. Rule-based signal  
   An interpretable conclusion produced by a predefined methodology rule.

5. Missing or unavailable state  
   A transparent indicator that sufficient evidence was not available.

The UI should reflect this distinction clearly.

## Entity coverage
The platform focuses on UK registered entities available through supported data sources.

The platform can show:
- active companies
- dissolved companies where the source data supports it
- filing history
- officers
- persons with significant control
- charges
- insolvency-related data where available
- filed account-derived metrics where extractable

The platform cannot guarantee:
- full coverage of every document format
- perfect completeness for every financial field
- perfect continuity across all historical periods

## Data freshness methodology

### Search results
Search results are cached briefly to improve speed and protect rate limits.

### Company profile and governance panels
These are refreshed on a daily basis or sooner when a watchlist-triggered refresh occurs.

### Filing-derived financial facts
Financial facts are refreshed when:
- a company is first ingested
- a new filing is detected
- a manual refresh is requested
- parser logic is updated and a re-parse is triggered

### Freshness labelling
The UI should disclose:
- last successful refresh time
- source filing date for each major financial period
- whether values are current, historical, or comparative

## Financial analysis methodology

### General approach
Financial analysis is based only on fields that can be linked to source evidence with adequate confidence.

Values are not invented. Where evidence is absent or low confidence, the platform should show:
- unavailable
- low confidence
- partial coverage

### Canonical metrics
The platform should attempt to standardise the following where available:
- revenue
- gross profit
- operating profit or loss
- profit or loss after tax
- current assets
- fixed assets
- total assets less current liabilities
- creditors due within one year
- creditors due after one year
- net assets or liabilities
- cash at bank and in hand
- average number of employees

### Derived financial metrics
Where the relevant base facts exist, the platform may calculate:

#### Revenue growth
```text
(current_period_revenue - prior_period_revenue) / prior_period_revenue
```

#### Net assets growth
```text
(current_net_assets - prior_net_assets) / prior_net_assets
```

#### Profit margin
```text
profit_after_tax / revenue
```

#### Liquidity proxy
```text
current_assets / creditors_due_within_one_year
```

#### Leverage proxy
```text
(creditors_due_within_one_year + creditors_due_after_one_year) / max(net_assets, small_floor_value)
```

### Methodological cautions
- These are practical public-data indicators, not audited lending ratios
- They may be unavailable for some small or dormant companies
- Micro-entity accounts often provide limited disclosure
- Different filing regimes reduce direct comparability across companies

## Governance methodology

### Officers
The platform should show:
- current officers
- appointment dates
- resignation activity
- role types where available

### Governance indicators
Derived governance indicators may include:
- officer churn in trailing 12 months
- average current officer tenure
- presence of recent appointment spikes
- board stability versus board turnover patterns

### Persons with significant control
The platform should show:
- current PSC records where available
- nature of control
- change events when historically detectable

### Charges
The platform should show:
- outstanding charges count
- satisfied charges count
- recent charge registrations
- recent satisfaction events

Charges are interpreted as financing-related context, not automatically as negative evidence.

## Filing behaviour methodology

### Filing timeliness
Indicators may consider:
- overdue accounts state
- overdue confirmation statement state where available
- repeated late filing behaviour
- gaps in expected filing cadence

### Filing quality / completeness
Indicators may consider:
- availability of structured account data
- continuity of filed periods
- presence of amended filings
- unsupported or unreadable financial document formats

## Rule-based signal methodology

### Principles
Signals must be:
- explainable
- deterministic
- evidence-linked
- severity-rated
- reviewable and editable by developers

Signals must not:
- imply certainty beyond the evidence
- present themselves as regulated scores
- collapse many weak facts into an opaque single “truth” value

### Signal categories
- filing risk
- financial risk
- governance risk
- financing dependency signal
- opportunity / positive momentum signal
- confidence warning

### Example signal rules

#### Overdue accounts
Condition:
- company profile indicates accounts overdue

Severity:
- high

Evidence:
- official company profile field and due date

#### Negative net assets
Condition:
- latest extracted net assets below zero with medium or high confidence

Severity:
- high

Evidence:
- latest financial period facts and filing source

#### Officer churn spike
Condition:
- two or more officer changes in trailing 12 months

Severity:
- medium

Evidence:
- officer appointments and resignations history

#### Rapid revenue growth
Condition:
- revenue growth above configured threshold and no obvious confidence issues

Severity:
- informational / opportunity

Evidence:
- current and prior revenue facts

#### Limited confidence warning
Condition:
- major financial fields unavailable or mostly low confidence

Severity:
- informational

Evidence:
- parser coverage and confidence profile

## Confidence methodology

### Why confidence exists
Public filing extraction is not equally reliable across all formats. Confidence communicates extraction quality, not business quality.

### Confidence bands
- High: strong structured evidence
- Medium: credible evidence with some interpretation
- Low: ambiguous evidence or partial extraction
- Unavailable: insufficient evidence

### What confidence does not mean
A low-confidence extraction does not mean the company is risky.
A high-confidence extraction does not mean the company is healthy.

Confidence refers only to the reliability of the extracted data point or derived metric.

## Comparability methodology

### Cross-company comparison caveats
Comparison between companies should account for:
- different entity sizes
- different account disclosure regimes
- different filing dates
- dormant versus trading status
- different industries and capital structures

### Sector benchmarking
If sector benchmarking is added later:
- benchmark only against compatible sectors or filtered peer groups
- show sample size
- disclose benchmark date range
- avoid overprecision on small peer groups

## Missing data policy
Missing data must never be silently converted into:
- zero
- neutral
- low risk

Instead, show:
- unavailable
- not disclosed
- not extractable
- insufficient confidence

## User-facing explanation standards
Every important panel should answer:
- what this shows
- where it came from
- how recent it is
- how confident we are
- what the caveat is

## Legal and ethical position
The platform should state clearly:
- data is sourced from public records
- public records may be incomplete, delayed, or inconsistent
- outputs are informational only
- users should seek professional advice for investment, accounting, legal, tax, or lending decisions

## Auditability requirements
For every displayed signal or metric, the system should preserve:
- source company number
- source filing id
- source document id where relevant
- parser version
- extraction run id
- methodology version
- timestamp of generation

## Methodology versioning
This document should be versioned.

Changes requiring a version increment:
- metric formula changes
- signal threshold changes
- canonical fact mapping changes
- confidence scoring changes
- peer benchmark logic changes

Recommended fields:
- methodology_version
- effective_date
- release_notes

## MVP methodology scope
Include:
- source classification
- canonical financial metrics
- derived metrics with simple formulas
- transparent rules-based signals
- confidence bands
- caveat-first UX

Exclude initially:
- black-box machine learning scores
- probabilistic insolvency prediction claims
- investment recommendation language
- “safe to invest” or “good company” labels

## Future methodology enhancements
Later versions may add:
- sector medians and percentile benchmarking
- trend decomposition
- anomaly detection
- relationship graphs for officers and PSCs
- scenario-based scoring for specific user personas

These should only be added when they remain explainable and evidence-linked.
