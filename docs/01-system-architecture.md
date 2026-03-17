# CompanyScope System Architecture

## Purpose
This document defines the recommended system architecture for an open-source UK company intelligence platform built primarily on top of Companies House public data.

## Architectural stance
The platform should optimise for:
- source traceability
- explainable analytics
- graceful degradation when filings are incomplete
- low operational complexity at MVP
- future expansion to bulk ingestion and near-real-time monitoring

## Recommended stack
### Frontend
- Next.js 15
- TypeScript
- Tailwind CSS
- shadcn/ui
- TanStack Query
- Recharts
- Zod

### Backend and data services
- FastAPI
- Pydantic
- SQLAlchemy 2.x
- PostgreSQL 16
- Redis 7
- Celery or Dramatiq
- MinIO for S3-compatible object storage

### Platform and operations
- Docker Compose for local development
- GitHub Actions for CI
- OpenTelemetry
- Prometheus + Grafana + Loki
- OpenTofu for infrastructure as code in later phases

## Why this architecture
The hardest part of the product is not search UI. It is the ingestion and interpretation of filings, document retrieval, financial extraction, period normalisation, and transparent signal generation.

A Python backend is the best fit because it gives strong support for:
- document parsing
- iXBRL and HTML processing
- validation and ETL
- analytics and batch processing
- rules-based signal generation

The frontend should remain TypeScript-first because the user-facing product needs:
- fast iteration in Cursor
- typed API contracts
- good SSR and SEO for public company pages
- a mature ecosystem for dashboards and interaction patterns

## Companies House constraints that shape the design
The official developer documentation confirms the following:
- the Public Data API uses HTTP Basic authentication with the API key as the username
- the public API is rate-limited to 600 requests per 5 minutes per application
- the Document API is separate and document retrieval is driven by document metadata and content fetch endpoints
- the Streaming API is intended to keep an existing dataset current rather than replace a full base snapshot

These constraints mean the application must not call Companies House directly from the browser. All calls must go server-side with caching, background jobs, and backoff-aware refresh logic.

## High-level architecture
```text
┌─────────────────────────────────────────────────────────────┐
│                         Web Client                          │
│ Next.js app, SSR/ISR pages, authenticated dashboard, charts │
└───────────────┬─────────────────────────────────────────────┘
                │ HTTPS
                ▼
┌─────────────────────────────────────────────────────────────┐
│                    Application API Layer                    │
│ FastAPI: search, company aggregates, watchlists, alerts,    │
│ auth callbacks, admin endpoints, API schema validation      │
└───────┬──────────────────┬──────────────────┬───────────────┘
        │                  │                  │
        ▼                  ▼                  ▼
┌───────────────┐  ┌─────────────────┐  ┌────────────────────┐
│ PostgreSQL    │  │ Redis           │  │ Object Storage     │
│ canonical DB  │  │ cache + queues  │  │ MinIO cached docs  │
└───────┬───────┘  └────────┬────────┘  └─────────┬──────────┘
        │                   │                     │
        ▼                   ▼                     ▼
┌─────────────────────────────────────────────────────────────┐
│                  Background Worker Services                 │
│ ingestion, document fetch, parser, risk engine, alerts      │
└───────────────┬───────────────────────────┬─────────────────┘
                │                           │
                ▼                           ▼
┌──────────────────────────────┐  ┌──────────────────────────┐
│ Companies House Public APIs  │  │ Optional Bulk Datasets   │
│ search, profile, filings,    │  │ accounts archives, later │
│ officers, PSC, charges, docs │  │ historical backfills     │
└──────────────────────────────┘  └──────────────────────────┘
```

## Core services
### 1. Web application
Responsibilities:
- search interface
- company profile pages
- financial charts
- methodology pages
- watchlist and alerts UI
- authenticated user workspace

Rendering approach:
- public company pages should use server rendering or ISR-like caching
- authenticated pages should use client-side hydration with TanStack Query
- search autocomplete should be API-backed and cached aggressively

### 2. Application API
Responsibilities:
- user-facing endpoints for search and company data
- orchestration of stale-vs-fresh reads
- auth session handling
- watchlists and notification preferences
- rate limiting and abuse prevention
- API documentation generation

Rules:
- never expose Companies House API keys to the frontend
- every external call must pass through backend adapters
- every response should include freshness metadata and confidence context where relevant

### 3. Ingestion service
Responsibilities:
- fetch company profile
- fetch filing history
- fetch officers, PSCs, charges, insolvency data
- decide what needs downstream processing
- upsert canonical records

Trigger modes:
- on-demand when a company page is opened and cache is stale
- scheduled refresh for watchlisted companies
- event-driven refresh in later phases from Streaming API events

### 4. Document fetch service
Responsibilities:
- fetch document metadata
- fetch supported representations of the filing document
- persist the original or transformed asset in object storage
- update parser job queue

Important design choice:
- documents should be cached by content hash or document ID
- document processing must be idempotent
- unsupported content types should be stored as metadata-only with a parse status of `unsupported`

### 5. Financial parser service
Responsibilities:
- extract values from supported iXBRL, XBRL, and HTML accounts documents
- map raw labels to canonical financial facts
- validate consistency where possible
- emit confidence scores and parser warnings

Parser design principles:
- prefer tagged values over heuristic text scraping
- preserve original raw labels
- support multiple filing styles: micro-entity, small, abridged, full, LLP variants where feasible
- never turn missing values into zero

### 6. Risk rules engine
Responsibilities:
- compute explainable, non-black-box signals
- classify severity
- link each signal to evidence and filing dates
- regenerate signals when new facts arrive

Examples:
- accounts overdue
- confirmation statement overdue
- negative net assets
- officer churn spike
- recent charge registration activity
- repeated late filing pattern
- low-confidence financial extraction warning

### 7. Notification service
Responsibilities:
- process watchlist subscriptions
- email new filing alerts
- notify on overdue filings, charges, officer changes, and insolvency events
- later support webhooks and team notifications

## Deployment topology
### MVP deployment
Use a single environment with the following containers:
- `web`
- `api`
- `worker`
- `postgres`
- `redis`
- `minio`
- `prometheus`
- `grafana`
- `loki`
- `reverse-proxy`

This keeps operations simple while preserving clean service boundaries.

### Later scale-out
Split by workload:
- public web tier
- API tier
- worker tier
- parsing tier for CPU-heavy extraction
- dedicated object storage and managed database

## Request and processing flows
### Flow A: company search
1. user types a company name or company number
2. frontend calls `GET /api/v1/search`
3. API checks Redis cache
4. if cache miss, backend queries Companies House search endpoint
5. results are normalised and cached briefly
6. response returns ranked matches with status badges

### Flow B: open a company page
1. user opens `/company/{company_number}`
2. frontend requests aggregate company payload
3. API checks `company_snapshots` for a fresh aggregate
4. if fresh, it returns the cached aggregate immediately
5. if stale or missing, it returns available data and enqueues a refresh job
6. ingestion service refreshes profile, filings, governance records, and financials
7. parser and risk engine update downstream tables
8. company snapshot is rebuilt

### Flow C: document parsing
1. ingestion identifies an accounts-related filing
2. document metadata is resolved
3. the best supported representation is downloaded
4. document is stored in object storage
5. parser extracts raw and canonical facts
6. validation rules produce warnings or confidence downgrades
7. facts are written to period-based tables
8. risk rules recompute signals for the company

### Flow D: watchlist refresh
1. scheduler scans watchlisted companies due for refresh
2. refresh jobs are dispatched with jitter to avoid burst traffic
3. changed data triggers signal diffs and notifications
4. user receives email or in-app notification

## Caching strategy
### Redis cache classes
#### Search cache
- TTL: 10 to 15 minutes
- key: `search:{query_hash}`
- purpose: absorb repeated lookup traffic

#### Company aggregate cache
- TTL: 24 hours by default
- key: `company:aggregate:{company_number}`
- purpose: serve company pages quickly

#### Reference cache
- long-lived cache for SIC metadata and derived lookup tables

### Database snapshots
A denormalised `company_snapshots` table should hold the latest assembled view used by the UI. This is not a source of truth table. It is a read model rebuilt from canonical entities.

## Freshness model
Each company payload should return:
- `snapshot_generated_at`
- `source_last_checked_at`
- `staleness_status`
- `financials_confidence`
- `methodology_version`

Suggested states:
- `fresh`
- `stale`
- `refreshing`
- `partial`

## Data modelling philosophy
Use two layers:

### Canonical source layer
Stores the closest possible representation of official entities and events.
Examples:
- company core profile
- filing records
- officers and appointments
- PSCs
- charges
- insolvency cases
- raw extracted financial facts

### Product read model layer
Stores denormalised aggregates optimised for UI and API speed.
Examples:
- company snapshot JSON
- precomputed chart series
- risk summary cards
- watchlist status summaries

This separation avoids coupling the UI to raw source structures.

## Background jobs
Suggested job queues:
- `company_refresh`
- `document_fetch`
- `document_parse`
- `risk_recompute`
- `watchlist_refresh`
- `send_notifications`
- `rebuild_snapshots`

Each job must be:
- idempotent
- retry-safe
- traceable by company number and request ID

## Security architecture
### Principles
- server-side only access to external APIs
- least privilege access for internal services
- immutable audit trail for admin actions and important data operations
- strong input validation everywhere

### Auth
Recommended approach:
- Auth.js or Better Auth with email magic links first
- optional Google/GitHub OAuth for convenience
- signed session cookies
- backend authorisation checks on all watchlist and account resources

### API protection
- IP- and user-based rate limiting
- request validation with Pydantic and Zod
- bot mitigation for search abuse
- anti-enumeration controls for user resources
- CSRF protections on auth-sensitive POST endpoints

## Legal and product trust architecture
The UI and API should keep a strict distinction between:
- official source facts
- extracted or normalised values
- derived ratios
- risk signals
- editorial copy or explanatory text

Every signal should expose:
- severity
- explanation
- evidence links
- calculation timestamp
- methodology version

## Observability
### Metrics
Track:
- Companies House request volume
- cache hit rate
- document fetch success rate
- parser success rate
- parser coverage by metric type
- job queue latency
- API latency by endpoint
- snapshot rebuild duration

### Logging
Every important action should include:
- request ID
- company number
- job ID
- document ID if applicable
- parser version
- methodology version

### Tracing
Use OpenTelemetry end-to-end for:
- web request to API
- API to worker enqueue
- worker to external API call
- worker to database writes

## Failure handling
### Principles
- partial data is better than false certainty
- missing data must never be silently imputed for user-facing metrics
- parser failures should not break the company page

### Response behaviour
If financial parsing fails:
- still show company profile, filings, officers, and charges
- mark financial panels as unavailable or low confidence
- expose a parser status note

If Companies House rate limits are hit:
- serve stale cache where possible
- enqueue delayed refresh
- return controlled refresh messaging in the UI

## Architecture decisions
### Decision 1: monolith plus workers, not microservices
Reason:
- simpler operationally
- faster to build in Cursor
- still cleanly modular

### Decision 2: PostgreSQL as the primary source of truth
Reason:
- rich relational modelling
- strong JSON support for snapshots
- easy migrations and reporting

### Decision 3: period-based financial facts instead of only latest metrics
Reason:
- historical trends matter
- restatements happen
- parser upgrades should not overwrite auditability

### Decision 4: rule-based signals before ML scoring
Reason:
- easier to explain
- safer legally
- faster to validate

## Scalability path
### Stage 1
- live on-demand fetches
- company-level caching
- limited watchlists

### Stage 2
- scheduled refreshes
- more supported filing formats
- sector benchmarking tables

### Stage 3
- bulk data backfills
- Streaming API listener
- graph relationships between officers and related companies
- external API product

## Recommended folder structure for implementation
```text
apps/
  web/
  api/
  worker/
packages/
  schemas/
  ui/
  config/
  methodology/
infra/
  docker/
  opentofu/
docs/
  01-system-architecture.md
  02-database-schema.md
  03-api-spec.md
  04-cursor-build-plan.md
```

## Final recommendation
Build a transparent intelligence platform with a single deployable application boundary, worker-based ingestion, canonical storage in PostgreSQL, object-backed document caching, and an explicitly explainable signal engine.

That gives you the best balance of:
- speed to MVP
- open-source friendliness
- operational simplicity
- future scalability
- user trust
