# Financial Analysis Spec

## Purpose

This document defines exactly how CompanyScope derives metrics and signals from
extracted financial facts (`financial_periods` + `financial_facts`).

It is the authoritative specification for Phase 6 implementation.  All derived
metrics and signals must be traceable to this document via `methodology_version`.

**This layer is deterministic and non-advisory.**  It does not interpret
business quality.  It converts structured numerical evidence into labelled
calculations and pre-defined rule outcomes.

---

## Methodology version

`METHODOLOGY_VERSION = "1.0.0"`

Increment the minor version when thresholds change.  Increment the major
version when a formula changes.

---

## Inputs

All derived work reads from:

| Table | Key fields used |
|---|---|
| `financial_periods` | `period_end`, `period_start`, `period_length_days`, `currency_code`, `accounts_type`, `extraction_confidence` |
| `financial_facts` | `fact_name`, `fact_value`, `extraction_confidence`, `extraction_method`, `unit`, `source_document_id` |
| `companies` | `accounts_overdue`, `company_status`, `sic_codes` |
| `filings` | `action_date`, `description` |
| `officer_appointments` | `appointed_on`, `resigned_on`, `officer_role` |
| `charges` | `status`, `created_on` |

---

## Period selection rules

### Primary period

The **primary period** for a company is the most recent `financial_period`
whose `extraction_confidence >= 0.40` (i.e. confidence band ≥ low).

If multiple periods share the same `period_end`, prefer the one with highest
`extraction_confidence`.

### Prior period

The **prior period** is the most recent `financial_period` whose `period_end`
is strictly before the primary period's `period_end`, with
`extraction_confidence >= 0.40`.

Acceptable gap: prior `period_end` must fall within 18 months of primary
`period_start`.  Periods further apart are **not** used for growth calculations
(set metric to `null`; do not calculate across a data gap).

### Minimum confidence for metric calculation

| Metric category | Minimum fact confidence |
|---|---|
| Core balance-sheet metrics | 0.40 |
| Growth metrics (requires two periods) | 0.40 per period |
| Ratio metrics | 0.40 per input fact |

If any required input fact has `fact_value IS NULL` or falls below the minimum
confidence, the metric result is `null` — never defaulted to zero or estimated.

---

## Canonical facts used

All inputs are drawn from `financial_facts.fact_name`.  The 12 canonical names
are defined in `docs/05-parser-design.md §Canonical fact schema`.

Abbreviations used in formulas below:

| Abbreviation | `fact_name` |
|---|---|
| REV | `revenue` |
| GP | `gross_profit` |
| EBIT | `operating_profit_loss` |
| PAT | `profit_loss_after_tax` |
| CA | `current_assets` |
| FA | `fixed_assets` |
| TALCL | `total_assets_less_current_liabilities` |
| CDWOY | `creditors_due_within_one_year` |
| CDAOY | `creditors_due_after_one_year` |
| NAL | `net_assets_liabilities` |
| CASH | `cash_bank_on_hand` |
| EMP | `average_number_of_employees` |

---

## Core MVP derived metrics

These metrics are calculated for Phase 6A.  Each result is stored with
`fact_value`, `confidence`, `methodology_version`, and `period_id`.

### M1 — Gross profit margin

```
gross_profit_margin = GP / REV
```

- Unit: ratio (display as percentage)
- Guardrails:
  - If `REV == 0` or `REV IS NULL` → `null`
  - If `GP IS NULL` → `null`
  - Result clamped to `[-10, 10]`; values outside this range are stored with a
    `range_anomaly` warning and low confidence override
- Confidence: `min(conf(GP), conf(REV))`

### M2 — Operating profit margin

```
operating_profit_margin = EBIT / REV
```

- Unit: ratio
- Guardrails: same as M1; requires both `EBIT` and `REV`
- Confidence: `min(conf(EBIT), conf(REV))`

### M3 — Net profit margin

```
net_profit_margin = PAT / REV
```

- Unit: ratio
- Guardrails: same as M1
- Confidence: `min(conf(PAT), conf(REV))`

### M4 — Current ratio (liquidity proxy)

```
current_ratio = CA / CDWOY
```

- Unit: ratio
- Guardrails:
  - If `CDWOY == 0` or `CDWOY IS NULL` → `null`
  - If `CA IS NULL` → `null`
  - No clamping; values > 100 receive a `range_anomaly` warning
- Confidence: `min(conf(CA), conf(CDWOY))`
- Note: this is a solvency proxy from public accounts data, not the audited
  current ratio.  It is labelled accordingly in the UI.

### M5 — Cash as a share of current assets

```
cash_ratio = CASH / CA
```

- Unit: ratio
- Guardrails:
  - If `CA == 0` or `CA IS NULL` → `null`
  - If `CASH IS NULL` → `null`
  - Expected range `[0, 1]`; values outside receive `range_anomaly` warning
- Confidence: `min(conf(CASH), conf(CA))`

### M6 — Leverage proxy

```
leverage = (CDWOY + CDAOY) / max(NAL, 1)
```

- Unit: ratio
- Guardrails:
  - If both `CDWOY` and `CDAOY` are `null` → `null`
  - Use `0` for whichever creditor field is `null` **only when the other is
    present** (partial creditor disclosure is common in small accounts); record
    a `partial_input` warning in this case
  - If `NAL IS NULL` → `null`
  - `max(NAL, 1)` prevents divide-by-zero; do not use when `NAL <= 0` (result
    would be misleading) — instead set to `null` with a `negative_equity`
    warning
- Confidence: `min(conf(CDWOY or 0), conf(CDAOY or 0), conf(NAL))`

### M7 — Revenue growth (year-on-year)

```
revenue_growth = (REV_current - REV_prior) / abs(REV_prior)
```

- Unit: ratio
- Guardrails:
  - Requires both primary and prior period `REV`
  - If `REV_prior == 0` → `null`
  - If period gap > 18 months → `null` with `period_gap` warning
  - Result clamped to `[-1, 10]`; outside this range → store with
    `range_anomaly` warning
- Confidence: `min(conf(REV_current), conf(REV_prior))`

### M8 — Net assets growth (year-on-year)

```
net_assets_growth = (NAL_current - NAL_prior) / abs(NAL_prior)
```

- Unit: ratio
- Guardrails:
  - If `NAL_prior == 0` → `null`
  - If period gap > 18 months → `null`
  - No clamping; negative values are valid (equity erosion)
- Confidence: `min(conf(NAL_current), conf(NAL_prior))`

### M9 — Employee count change (year-on-year)

```
employee_growth = EMP_current - EMP_prior   (absolute, not ratio)
```

- Unit: count delta
- Guardrails:
  - Integer; stored as Decimal with 0dp
  - If either period `EMP` is `null` → `null`
- Confidence: `min(conf(EMP_current), conf(EMP_prior))`
- Note: employee data is often absent in micro/small accounts.

---

## Later-phase derived metrics (post-MVP)

These are defined but **not implemented in Phase 6A**.

| ID | Name | Formula sketch |
|---|---|---|
| M10 | Asset turnover | `REV / (FA + CA)` |
| M11 | Working capital | `CA - CDWOY` |
| M12 | Debt-to-equity | `(CDWOY + CDAOY) / NAL` |
| M13 | Gross profit growth | `(GP_current - GP_prior) / abs(GP_prior)` |
| M14 | Operating profit growth | `(EBIT_current - EBIT_prior) / abs(EBIT_prior)` |

These require the same guardrails as the core metrics.

---

## Confidence propagation for derived metrics

Derived metric confidence is always the **minimum** of the input fact
confidences.  It is never averaged up.

### Confidence band for derived metrics

| Score | Band |
|---|---|
| ≥ 0.85 | high |
| ≥ 0.65 | medium |
| ≥ 0.40 | low |
| < 0.40 | unavailable |

A derived metric with `unavailable` confidence **must not** be used as signal
input (the signal must fire only on medium or high confidence evidence, or
explicitly accept low confidence with a penalty).

---

## Null-handling rules

These rules are absolute.  They apply to every metric and signal.

1. **Never convert `null` to `0`.**  Missing evidence is not zero.
2. **Never calculate a ratio with a null numerator or denominator.**  Result is
   `null`.
3. **Never calculate growth across a period gap > 18 months.**  Result is
   `null` with a `period_gap` warning.
4. **Never produce a metric from facts with `extraction_confidence < 0.40`.**
   Result is `null` with a `low_source_confidence` warning.
5. **Partial input substitution** (using `0` for a missing creditor field)
   is only permitted for M6 and must be tagged with a `partial_input` warning.

---

## Rule-based signals

Signals are deterministic: given the same input data, the same signal always
fires or does not fire.  There is no probabilistic element.

Each signal produces:
- `signal_key` — unique identifier (e.g. `negative_net_assets`)
- `severity` — `high` | `medium` | `low` | `informational`
- `fired` — boolean
- `evidence` — JSON object linking to specific fact values and filing IDs
- `methodology_version`
- `generated_at`

### Signal minimum confidence requirement

Unless stated otherwise, a signal only fires when **all input facts or metrics
have confidence band ≥ medium (score ≥ 0.65)**.  Signals backed by low
confidence data are suppressed and replaced with a `data_quality_warning`
signal.

---

### S1 — Negative net assets

```
fired = NAL < 0
```

- Severity: **high**
- Minimum confidence: low (≥ 0.40) — negative equity is important even from
  lower-quality HTML extraction
- Evidence: `NAL` value, confidence, source filing

### S2 — Negative net assets, worsening

```
fired = NAL_current < NAL_prior < 0
```

- Severity: **high**
- Confidence requirement: medium on both periods
- Evidence: both `NAL` values, both filing IDs

### S3 — Significant revenue decline

```
fired = revenue_growth < -0.20
```

- Severity: **high** if `revenue_growth < -0.40`; **medium** if in `[-0.40, -0.20)`
- Confidence requirement: medium on both periods
- Evidence: both REV values, both filing IDs, computed growth rate

### S4 — Liquidity pressure

```
fired = current_ratio < 1.0
```

- Severity: **medium**
- Confidence requirement: medium
- Evidence: CA, CDWOY values, computed ratio

### S5 — Severe liquidity pressure

```
fired = current_ratio < 0.5
```

- Severity: **high**
- Confidence requirement: medium
- Evidence: CA, CDWOY values, computed ratio

### S6 — Cash concentration risk

```
fired = cash_ratio < 0.05 AND current_ratio < 1.2
```

Both conditions must be satisfied.

- Severity: **medium**
- Confidence requirement: medium on CASH and CA
- Evidence: CASH, CA values

### S7 — High leverage

```
fired = leverage > 3.0
```

- Severity: **medium**
- Confidence requirement: medium
- Evidence: CDWOY, CDAOY, NAL values, computed leverage

### S8 — Extreme leverage

```
fired = leverage > 10.0
```

- Severity: **high**
- Confidence requirement: medium
- Evidence: same as S7

### S9 — Accounts overdue

```
fired = companies.accounts_overdue = true
```

- Severity: **high**
- Source: company profile (not extracted; direct from Companies House API)
- No confidence requirement (source is structured API field)

### S10 — No accounts filed recently

```
fired = latest financial_period.period_end < today - 24 months
        OR no financial_period exists
```

- Severity: **medium**
- Source: financial_periods table + system clock
- Note: not the same as `accounts_overdue`; this detects parsing gaps

### S11 — Positive revenue momentum

```
fired = revenue_growth > 0.10 AND (EBIT > 0 OR EBIT IS NULL)
```

- Severity: **informational**
- Confidence requirement: medium
- Evidence: REV values, growth rate, EBIT if present
- Note: informational signals are not negative; they surface positive evidence

### S12 — Consistent profitability

```
fired = PAT_current > 0 AND PAT_prior > 0
```

- Severity: **informational**
- Confidence requirement: medium on both periods
- Evidence: both PAT values, both filing IDs

### S13 — Data quality warning

```
fired = majority of core facts are null OR extraction_confidence < 0.40
        for the primary period
```

"Majority" = 6 or more of the 12 canonical facts are `null` or
`extraction_confidence < 0.40`.

- Severity: **informational**
- Source: financial_facts coverage for the primary period

---

## Signal suppression rules

| Condition | Action |
|---|---|
| Input fact confidence < 0.40 | Suppress signal; fire S13 instead |
| No primary period exists | Suppress all financial signals; fire S10 |
| Company status = `dissolved` | Suppress S9 (overdue accounts); still show financial signals |
| `period_gap` warning on metric | Suppress growth signals S2, S3 |

---

## Storage: derived_metrics table

Derived metrics are stored separately from raw facts.

```sql
create table derived_metrics (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id),
  financial_period_id uuid references financial_periods(id),
  prior_period_id uuid references financial_periods(id),
  metric_key varchar(64) not null,
  metric_value numeric(20, 6),
  unit varchar(32),
  confidence numeric(5, 4),
  confidence_band varchar(16),
  warnings jsonb,
  methodology_version varchar(16) not null,
  generated_at timestamptz not null default now(),
  constraint uq_derived_metrics unique (company_id, financial_period_id, metric_key)
);
```

## Storage: risk_signals table

```sql
create table risk_signals (
  id uuid primary key default gen_random_uuid(),
  company_id uuid not null references companies(id),
  signal_key varchar(64) not null,
  fired boolean not null,
  severity varchar(16),
  evidence jsonb,
  methodology_version varchar(16) not null,
  generated_at timestamptz not null default now(),
  constraint uq_risk_signals unique (company_id, signal_key)
);
```

Both tables are rebuilt (upsert) on every metric recompute run triggered after
a new `financial_period` is ingested or when `METHODOLOGY_VERSION` changes.

---

## What this spec does not cover

- AI-generated narrative (see `docs/10-ai-analysis-layer-spec.md`)
- UI rendering of these metrics (see `docs/11-ui-ux-principles.md`)
- Benchmarking against sector peers (post-MVP)
- Multi-currency conversion (GBP only in MVP)
