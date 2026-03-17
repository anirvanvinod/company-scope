# CompanyScope Database Schema

## Purpose
This document defines the relational schema for the MVP and early scale phases of CompanyScope.

The schema is designed around three principles:
- preserve official source records
- store financial facts by period and evidence source
- support fast denormalised read models without losing auditability

## Recommended database
- PostgreSQL 16

## Schema strategy
Use a single PostgreSQL database with logical grouping by schema.

Suggested schemas:
- `app` for product-facing entities
- `ch_raw` for source-shaped Companies House entities
- `analytics` for derived facts and signals
- `ops` for audit and ingestion operations

For an MVP, you can keep everything in `public` and separate later if needed. The table design below works either way.

## Entity overview
```text
users ──< watchlists ──< watchlist_items >── companies
users ──< alert_channels

companies ──< company_snapshots
companies ──< filings ──< filing_documents
companies ──< officer_appointments >── officers
companies ──< psc_records
companies ──< charges
companies ──< insolvency_cases
companies ──< financial_periods ──< financial_facts
companies ──< risk_signals
companies ──< refresh_runs

filings ──< extraction_runs
filing_documents ──< extraction_runs
company_snapshots ──< snapshot_build_runs
```

## Core tables

## 1. companies
Canonical company identity and current profile.

```sql
create table companies (
  id uuid primary key,
  company_number varchar(16) not null unique,
  company_name text not null,
  jurisdiction varchar(64),
  company_status varchar(64),
  company_type varchar(64),
  subtype varchar(64),
  date_of_creation date,
  cessation_date date,
  has_insolvency_history boolean,
  has_charges boolean,
  accounts_next_due date,
  accounts_overdue boolean,
  confirmation_statement_next_due date,
  confirmation_statement_overdue boolean,
  registered_office_address jsonb,
  sic_codes text[],
  source_etag text,
  source_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_companies_name on companies using gin (to_tsvector('simple', company_name));
create index idx_companies_status on companies (company_status);
```

Notes:
- `company_number` should be the main business key.
- `registered_office_address` can remain JSONB initially.
- keep current due dates here because they are frequently shown in the UI.

## 2. company_snapshots
Denormalised read model for fast page rendering.

```sql
create table company_snapshots (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  snapshot_version integer not null,
  methodology_version varchar(32) not null,
  parser_version varchar(32),
  freshness_status varchar(32) not null,
  snapshot_payload jsonb not null,
  snapshot_generated_at timestamptz not null,
  source_last_checked_at timestamptz,
  expires_at timestamptz,
  is_current boolean not null default true,
  created_at timestamptz not null default now()
);

create unique index uq_company_snapshots_current on company_snapshots(company_id) where is_current = true;
create index idx_company_snapshots_payload_gin on company_snapshots using gin (snapshot_payload);
```

Notes:
- Only one current snapshot per company.
- This is the UI read model, not the source of truth.

## 3. filings
Filing history items from Companies House.

```sql
create table filings (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  transaction_id varchar(64) not null,
  category varchar(64),
  type varchar(32),
  description text,
  description_values jsonb,
  action_date date,
  date_filed date,
  pages integer,
  barcode text,
  paper_filed boolean,
  source_links jsonb,
  source_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, transaction_id)
);

create index idx_filings_company_action_date on filings (company_id, action_date desc);
create index idx_filings_category on filings (category);
create index idx_filings_type on filings (type);
```

## 4. filing_documents
Document metadata and local caching status.

```sql
create table filing_documents (
  id uuid primary key,
  filing_id uuid not null references filings(id) on delete cascade,
  document_id varchar(128) not null unique,
  original_filename text,
  content_length bigint,
  content_type text,
  available_content_types text[],
  storage_key text,
  storage_etag text,
  fetch_status varchar(32) not null default 'pending',
  parse_status varchar(32) not null default 'pending',
  -- Populated by Phase 5A classifier: 'ixbrl', 'xbrl', 'html', 'pdf', 'unsupported'
  document_format varchar(32),
  downloaded_at timestamptz,
  metadata_payload jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_filing_documents_filing on filing_documents (filing_id);
create index idx_filing_documents_status on filing_documents (fetch_status, parse_status);
```

## 5. officers
Person or corporate officer entity.

```sql
create table officers (
  id uuid primary key,
  officer_external_id text,
  name text not null,
  officer_role varchar(64),
  nationality text,
  occupation text,
  country_of_residence text,
  date_of_birth_month smallint,
  date_of_birth_year smallint,
  kind varchar(32),
  raw_payload jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_officers_name on officers using gin (to_tsvector('simple', name));
```

Notes:
- date of birth should not be stored more precisely than the source exposes.
- keep the raw payload for auditability.

## 6. officer_appointments
Join table linking officers to companies across appointments.

```sql
create table officer_appointments (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  officer_id uuid not null references officers(id) on delete cascade,
  appointment_id text,
  role varchar(64),
  appointed_on date,
  resigned_on date,
  is_pre_1992_appointment boolean,
  address jsonb,
  source_last_checked_at timestamptz,
  raw_payload jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, officer_id, role, appointed_on)
);

create index idx_officer_appointments_company on officer_appointments (company_id);
create index idx_officer_appointments_active on officer_appointments (company_id, resigned_on);
```

## 7. psc_records
Persons with significant control.

```sql
create table psc_records (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  psc_external_id text,
  kind varchar(64),
  name text,
  notified_on date,
  ceased_on date,
  nationality text,
  country_of_residence text,
  date_of_birth_month smallint,
  date_of_birth_year smallint,
  natures_of_control text[],
  address jsonb,
  raw_payload jsonb,
  source_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_psc_records_company on psc_records (company_id);
create index idx_psc_records_active on psc_records (company_id, ceased_on);
```

## 8. charges
Registered charges and related activity.

```sql
create table charges (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  charge_id text not null,
  status varchar(64),
  delivered_on date,
  created_on date,
  resolved_on date,
  persons_entitled jsonb,
  particulars jsonb,
  raw_payload jsonb,
  source_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, charge_id)
);

create index idx_charges_company on charges (company_id);
create index idx_charges_status on charges (status);
```

## 9. insolvency_cases
Public insolvency case records where available.

```sql
create table insolvency_cases (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  case_number text,
  case_type varchar(64),
  petition_date date,
  order_date date,
  notes jsonb,
  practitioner jsonb,
  raw_payload jsonb,
  source_last_checked_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_insolvency_cases_company on insolvency_cases (company_id);
```

## Financial modelling tables

## 10. financial_periods
Represents a reporting period for one company.

```sql
create table financial_periods (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  filing_id uuid references filings(id) on delete set null,
  period_start date,
  period_end date not null,
  period_length_days integer,
  accounts_type varchar(64),
  accounting_standard varchar(64),
  currency_code char(3) default 'GBP',
  is_restated boolean not null default false,
  comparison_period_end date,
  source_document_id uuid references filing_documents(id) on delete set null,
  extraction_confidence numeric(5,4),
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(company_id, period_end, accounts_type)
);

create index idx_financial_periods_company on financial_periods (company_id, period_end desc);
```

## 11. financial_facts
Canonical period-based financial facts.

```sql
create table financial_facts (
  id uuid primary key,
  financial_period_id uuid not null references financial_periods(id) on delete cascade,
  company_id uuid not null references companies(id) on delete cascade,
  fact_name varchar(128) not null,
  fact_value numeric(20,2),
  unit varchar(32) default 'GBP',
  raw_label text,
  canonical_label varchar(128),
  source_document_id uuid references filing_documents(id) on delete set null,
  source_filing_id uuid references filings(id) on delete set null,
  extraction_method varchar(64),
  extraction_confidence numeric(5,4),
  is_derived boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  unique(financial_period_id, fact_name)
);

create index idx_financial_facts_company_fact on financial_facts (company_id, fact_name);
create index idx_financial_facts_period on financial_facts (financial_period_id);
```

Recommended `fact_name` values for MVP:
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

Note: names align with docs/05-parser-design.md canonical fact schema and docs/decisions/001-canonical-fact-names.md (resolved Phase 1B).

## Analytics tables

## 12. risk_signals
Transparent, rule-based company signals.

```sql
create table risk_signals (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  signal_code varchar(64) not null,
  signal_name text not null,
  category varchar(64) not null,
  severity varchar(16) not null,
  status varchar(16) not null default 'active',
  explanation text not null,
  evidence jsonb,
  methodology_version varchar(32) not null,
  first_detected_at timestamptz not null,
  last_confirmed_at timestamptz not null,
  resolved_at timestamptz,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_risk_signals_company on risk_signals (company_id, status, severity);
create index idx_risk_signals_code on risk_signals (signal_code);
```

Examples of `signal_code`:
- ACCOUNTS_OVERDUE
- CONFIRMATION_STATEMENT_OVERDUE
- NEGATIVE_NET_ASSETS
- OFFICER_CHURN_SPIKE
- RECENT_CHARGE_ACTIVITY
- LOW_FINANCIAL_CONFIDENCE

## 13. metric_series_cache
Optional precomputed chart series for frontend speed.

```sql
create table metric_series_cache (
  id uuid primary key,
  company_id uuid not null references companies(id) on delete cascade,
  metric_name varchar(128) not null,
  methodology_version varchar(32) not null,
  series_payload jsonb not null,
  generated_at timestamptz not null,
  expires_at timestamptz,
  unique(company_id, metric_name, methodology_version)
);
```

## Product tables

## 14. users
Minimal application user table.

```sql
create table users (
  id uuid primary key,
  email citext not null unique,
  display_name text,
  auth_provider varchar(32) not null,
  auth_subject text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## 15. watchlists
User-owned list of companies.

```sql
create table watchlists (
  id uuid primary key,
  user_id uuid not null references users(id) on delete cascade,
  name text not null,
  description text,
  is_default boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create index idx_watchlists_user on watchlists (user_id);
```

## 16. watchlist_items
Items inside a watchlist.

```sql
create table watchlist_items (
  id uuid primary key,
  watchlist_id uuid not null references watchlists(id) on delete cascade,
  company_id uuid not null references companies(id) on delete cascade,
  monitoring_status varchar(32) not null default 'active',
  last_refresh_at timestamptz,
  created_at timestamptz not null default now(),
  unique(watchlist_id, company_id)
);

create index idx_watchlist_items_company on watchlist_items (company_id);
```

## 17. alert_channels
User notification preferences.

```sql
create table alert_channels (
  id uuid primary key,
  user_id uuid not null references users(id) on delete cascade,
  channel_type varchar(32) not null,
  destination text not null,
  is_verified boolean not null default false,
  is_enabled boolean not null default true,
  preferences jsonb,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);
```

## Operational tables

## 18. refresh_runs
Tracks company refresh attempts.

```sql
create table refresh_runs (
  id uuid primary key,
  -- Nullable: full refreshes (trigger_type='full') create the run before the
  -- company_id is known.  Partial refreshes always set this to a real UUID.
  company_id uuid references companies(id) on delete cascade,
  trigger_type varchar(32) not null,
  requested_by_user_id uuid references users(id) on delete set null,
  status varchar(32) not null,
  started_at timestamptz not null,
  finished_at timestamptz,
  error_summary text,
  metadata jsonb,
  created_at timestamptz not null default now()
);

create index idx_refresh_runs_company on refresh_runs (company_id, started_at desc);
```

## 19. extraction_runs
Tracks document parsing attempts.

```sql
create table extraction_runs (
  id uuid primary key,
  filing_id uuid references filings(id) on delete set null,
  filing_document_id uuid references filing_documents(id) on delete set null,
  parser_version varchar(32) not null,
  -- Format detected at time of run: 'ixbrl', 'xbrl', 'html', 'pdf', 'unsupported'
  document_format varchar(32),
  status varchar(32) not null,
  confidence numeric(5,4),
  warnings jsonb,
  errors jsonb,
  started_at timestamptz not null,
  finished_at timestamptz,
  created_at timestamptz not null default now()
);

create index idx_extraction_runs_document on extraction_runs (filing_document_id, started_at desc);
```

## 20. audit_events
Immutable audit trail for key product and admin actions.

```sql
create table audit_events (
  id uuid primary key,
  actor_user_id uuid references users(id) on delete set null,
  actor_type varchar(32) not null,
  event_type varchar(64) not null,
  entity_type varchar(64) not null,
  entity_id text not null,
  event_payload jsonb,
  created_at timestamptz not null default now()
);

create index idx_audit_events_entity on audit_events (entity_type, entity_id, created_at desc);
```

## Derived view suggestions

## 1. active_officers_view
```sql
create view active_officers_view as
select *
from officer_appointments
where resigned_on is null;
```

## 2. latest_financial_period_view
```sql
create view latest_financial_period_view as
select distinct on (company_id)
  *
from financial_periods
order by company_id, period_end desc;
```

## 3. current_risk_summary_view
```sql
create view current_risk_summary_view as
select
  company_id,
  count(*) filter (where status = 'active' and severity = 'high') as high_count,
  count(*) filter (where status = 'active' and severity = 'medium') as medium_count,
  count(*) filter (where status = 'active' and severity = 'low') as low_count
from risk_signals
group by company_id;
```

## Snapshot payload shape recommendation
The `company_snapshots.snapshot_payload` should contain only data needed for immediate rendering.

Suggested top-level keys:
```json
{
  "company": {},
  "overview": {},
  "filing_summary": {},
  "financial_summary": {},
  "charts": {},
  "signals": [],
  "officers": [],
  "psc": [],
  "charges": [],
  "insolvency": [],
  "freshness": {},
  "confidence": {}
}
```

## Data integrity rules
- a company must exist before any filing, officer appointment, charge, or financial fact is inserted
- `financial_facts.company_id` must match the company on `financial_periods`
- `company_snapshots.is_current` must be unique per company
- `watchlist_items` must be unique per watchlist and company
- parser and methodology versions should be stored on every derived artefact

## Suggested enums
Use PostgreSQL enums only if your team is comfortable with migration overhead. Otherwise use checked varchar values.

Suggested controlled vocabularies:
- `freshness_status`: fresh, stale, refreshing, partial
- `fetch_status`: pending, fetched, unavailable, failed
- `parse_status`: pending, classified, parsed, unsupported, failed
  - `classified` — Phase 5A: format detected; awaiting Phase 5B extraction
- `document_format`: ixbrl, xbrl, html, pdf, unsupported
- `severity`: low, medium, high
- `status`: active, resolved, suppressed

## Migration order
1. users, watchlists, alert_channels
2. companies
3. filings and filing_documents
4. officers and officer_appointments
5. psc_records, charges, insolvency_cases
6. financial_periods and financial_facts
7. risk_signals and metric_series_cache
8. company_snapshots
9. operational tables

## Partitioning advice
You do not need partitioning for the MVP.

Introduce partitioning later for:
- `audit_events`
- `refresh_runs`
- `extraction_runs`
- potentially `financial_facts` if your volume grows very large

## Retention advice
- retain canonical source entities indefinitely
- retain snapshots for a rolling period or keep only current plus periodic history
- retain audit and extraction runs according to operational policy
- never delete user data without a clear retention and privacy policy

## Final recommendation
This schema gives you:
- auditability
- historical financial trends
- explainable derived signals
- fast company pages
- room to scale into watchlists, comparisons, and alerts

The most important modelling decision is period-based financial facts linked to source filings and documents. That is what will make your product reliable instead of just attractive.
