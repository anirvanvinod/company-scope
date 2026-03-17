# CompanyScope Cursor Build Plan

## Purpose
This document turns the product design into a practical, Cursor-friendly build sequence.

The goal is not only to define what to build, but also the order in which to build it so that:
- you get visible progress quickly
- technical debt stays controlled
- the hardest data problems are isolated early
- the codebase remains understandable to future contributors

## Recommended project strategy
Build this in four layers:
1. shell product and developer foundation
2. data ingestion and storage foundation
3. user-facing company intelligence flows
4. alerts, comparisons, and hardening

Do not start with perfect parsing or large-scale data coverage. Start with a trustworthy product skeleton that can improve over time.

## Recommended monorepo layout
```text
companyscope/
  apps/
    web/
    api/
    worker/
  packages/
    ui/
    schemas/
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

## Recommended package responsibilities
### apps/web
- Next.js app
- search UI
- company page UI
- watchlist UI
- authenticated settings UI

### apps/api
- FastAPI routes
- domain services
- Companies House adapters
- auth middleware
- snapshot builders

### apps/worker
- queue consumers
- ingestion orchestration
- document fetch
- parsing
- risk computation
- notifications

### packages/schemas
- shared JSON schemas
- generated API types
- shared enums and constants

### packages/methodology
- signal definitions
- metric definitions
- parser confidence notes
- version metadata

## Build sequence

## Phase 0: setup and guardrails
### Goal
Get the repo, local stack, and coding conventions ready before building features.

### Build tasks
- initialise monorepo structure
- set up pnpm or npm workspaces plus Python virtual environment tooling
- create Docker Compose for Postgres, Redis, MinIO, API, worker, and web
- add linting and formatting for TypeScript and Python
- add pre-commit hooks
- configure environment variable strategy
- set up GitHub Actions CI for web and backend checks

### Deliverables
- working local `docker compose up`
- empty web page
- empty FastAPI app with `/health`
- empty worker boot process

### Cursor prompt
```text
Create the initial monorepo structure for CompanyScope with:
- Next.js app in apps/web
- FastAPI app in apps/api
- Python worker app in apps/worker
- shared packages folder
- Docker Compose for postgres, redis, minio
- README with startup instructions
Use TypeScript for the web app, Python 3.12 for API and worker, and make the structure production-friendly.
```

## Phase 1: schema and persistence foundation
### Goal
Make the data model real before touching feature complexity.

### Build tasks
- implement SQLAlchemy models for core tables
- create Alembic migrations
- wire database session management
- add seed support for methodology versions and signal definitions
- create repository layer or service abstractions for company, filing, officer, and financial entities

### Deliverables
- reproducible migrations
- local database schema
- test that can insert and fetch a company snapshot

### Cursor prompt
```text
Using the database schema document, implement SQLAlchemy 2.x models and Alembic migrations for:
- companies
- company_snapshots
- filings
- filing_documents
- officers
- officer_appointments
- psc_records
- charges
- insolvency_cases
- financial_periods
- financial_facts
- risk_signals
- users
- watchlists
- watchlist_items
Make all relationships explicit and use sensible indexes.
```

## Phase 2: Companies House adapter layer
### Goal
Build a clean integration boundary with Companies House before building the UI.

### Build tasks
- create adapter module for Public Data API
- create adapter module for Document API
- centralise auth and retry logic
- centralise rate limit handling
- define typed response schemas with Pydantic
- implement a small caching layer for search and profile requests

### Deliverables
- search function
- company profile fetch function
- filing history fetch function
- officers fetch function
- PSC fetch function
- charges fetch function
- insolvency fetch function
- document metadata and content fetch functions

### Key rule
Never let raw external API shapes leak directly into application endpoints.

### Cursor prompt
```text
Build a Companies House integration layer in FastAPI with separate adapter modules for:
- company search
- company profile
- filing history
- officers
- PSC
- charges
- insolvency
- document metadata
- document content
Use HTTP Basic auth with the API key from environment variables, add retry and backoff logic, and return typed Pydantic models.
```

## Phase 3: ingestion pipeline
### Goal
Create the backend process that turns public records into your canonical database model.

### Build tasks
- implement company refresh orchestration
- implement upsert logic for core entities
- enqueue downstream jobs for document fetch and parsing
- implement refresh run logging
- add idempotency protection so repeated refreshes do not duplicate records

### Deliverables
- `ingest_company(company_number)` workflow
- company refresh endpoint for internal use
- refresh run tracking in DB

### Cursor prompt
```text
Create an ingestion orchestration service for CompanyScope.
The service should:
- accept a company number
- fetch company profile, filings, officers, PSCs, charges, and insolvency records
- upsert them into PostgreSQL
- create refresh_runs entries
- detect account-related filings and enqueue document fetch jobs
- be idempotent and safe to rerun
Use SQLAlchemy and a worker-compatible job design.
```

## Phase 4: document fetch and parser v1
### Goal
Prove that you can extract useful financial facts from supported account documents.

### Build tasks
- implement document metadata fetch and content download
- store document assets in MinIO
- build parser pipeline for supported iXBRL, XBRL, and HTML documents
- map raw labels to canonical fact names
- write period records and financial facts
- store extraction confidence and warnings

### Deliverables
- parser service with a clean interface
- first set of extracted metrics
- extraction run tracking

### Important scope boundary
For the first parser version, support only the content types and filing shapes you can reliably parse. Mark everything else as unsupported or low confidence.

### Cursor prompt
```text
Build parser v1 for CompanyScope financial documents.
Requirements:
- input is a cached filing document from MinIO plus metadata from PostgreSQL
- support structured iXBRL and HTML where tagged values exist
- extract canonical metrics such as revenue, gross profit, net assets, current assets, creditors due within one year, and cash at bank
- create financial_periods and financial_facts records
- emit extraction confidence scores and warnings
- never convert missing values into zero
Use Python, lxml or BeautifulSoup, and a clean service-oriented design.
```

## Phase 5: risk engine v1
### Goal
Turn raw facts into explainable signals.

### Build tasks
- define methodology versioning
- implement signal rules
- store evidence payloads
- compute active and resolved states
- add a service to recompute on demand

### MVP signal examples
- accounts overdue
- confirmation statement overdue
- negative net assets
- officer churn spike in last 12 months
- recent charge activity
- low financial confidence

### Deliverables
- risk signal generator
- methodology registry
- signal endpoint backing data

### Cursor prompt
```text
Implement a rule-based risk signal engine for CompanyScope.
Create rules for:
- accounts overdue
- confirmation statement overdue
- negative net assets
- recent charge activity
- officer churn spike
- low financial extraction confidence
Each signal must store severity, explanation, evidence, and methodology version.
```

## Phase 6: snapshot builder and public API
### Goal
Assemble fast read models for the UI and expose them through stable endpoints.

### Build tasks
- build company snapshot assembler
- populate company summary, filing summary, financial summary, signals, and freshness metadata
- expose the public endpoints described in the API spec
- add Redis-backed response caching where appropriate

### Deliverables
- `/api/v1/search`
- `/api/v1/companies/{company_number}`
- `/api/v1/companies/{company_number}/financials`
- `/api/v1/companies/{company_number}/filings`
- `/api/v1/companies/{company_number}/signals`

### Cursor prompt
```text
Implement the public API for CompanyScope based on the API specification.
Use FastAPI routers and Pydantic response models.
The main endpoint should return a denormalised company aggregate assembled from canonical tables and company snapshots.
Include freshness metadata and confidence information where relevant.
```

## Phase 7: frontend MVP
### Goal
Make the product usable and impressive without overbuilding.

### Build tasks
- landing page with company search
- company results dropdown
- company overview page
- filing timeline UI
- financial charts
- risk signals panel
- methodology page
- graceful states for missing or partial data

### UI rules
- every risk signal must be explainable
- every chart should show period ends clearly
- every page should show freshness and source caveats
- do not use alarmist copy

### Deliverables
- working search-to-company flow
- first polished public company page

### Cursor prompt
```text
Build the Next.js frontend for CompanyScope.
Requirements:
- homepage with company search and autocomplete
- company page with tabs for Overview, Financials, Filings, Officers, Ownership, Charges, and Risk Signals
- charts for revenue, net assets, and other available metrics
- freshness badge and confidence notes
- clean, premium, accessible UI using Tailwind and shadcn/ui
Use TanStack Query for data fetching.
```

## Phase 8: auth, watchlists, and alerts
### Goal
Add user retention features after the public product is working.

### Build tasks
- integrate auth provider
- implement user session handling
- add watchlist CRUD endpoints
- add watchlist UI
- implement email alerts for new filings and selected signals

### Deliverables
- sign-in flow
- save company to watchlist
- email alert preference flow

### Cursor prompt
```text
Add authenticated user features to CompanyScope.
Implement:
- email magic-link authentication
- user profile endpoint
- watchlists and watchlist items
- alert channels for email
- UI to save companies and manage notifications
Keep the product secure and simple.
```

## Phase 9: hardening and analytics
### Goal
Make the product production-ready.

### Build tasks
- observability stack
- structured logging and tracing
- endpoint rate limiting
- abuse prevention on search and refresh
- E2E tests for primary flows
- parser regression fixtures
- admin tools for reprocessing and health checks

### Deliverables
- dashboards for ingestion health and parser coverage
- test suite across search, company page, refresh, and watchlists
- incident-friendly logging

## Recommended backlog order within Cursor
When working interactively in Cursor, ask it to build in this order:
1. repo and infra skeleton
2. DB models and migrations
3. Companies House adapters
4. ingestion orchestration
5. parser v1
6. risk engine v1
7. snapshot builder and API
8. frontend MVP
9. auth and watchlists
10. observability and hardening

This order forces the data backbone to exist before the glossy UI.

## Definition of done for MVP
The MVP is done when a user can:
- search for a UK company
- open a company page
- see company status, filing timeline, officers, PSCs, charges, and insolvency panels
- see financial charts for supported filings
- see transparent risk signals with evidence
- save a company to a watchlist
- receive a basic alert when something important changes

## What to postpone
Do not build these in the first release:
- complex valuation modelling
- investment recommendation language
- machine learning risk scores
- semantic search over documents
- graph visualisation of related officers and companies
- bulk CSV export workflows
- team collaboration features

## Suggested coding rules for Cursor
### Backend rules
- keep external API adapters separate from business logic
- every service should be testable without the web app
- never mix parsing code into route handlers
- make every background task idempotent
- use Pydantic models for all boundary contracts

### Frontend rules
- fetch from your own API only
- keep components presentational where possible
- use typed hooks for all endpoints
- render missing data explicitly
- prefer SSR or cached server rendering for public pages

### General rules
- use request IDs everywhere
- version methodology and parser logic
- keep raw and derived data distinct
- document every non-obvious decision in `/docs`

## Suggested first eight GitHub issues
1. Initialise monorepo and Docker Compose stack
2. Implement PostgreSQL models and Alembic migrations
3. Add Companies House Public Data API adapter with auth and retry
4. Add company ingestion service and refresh job orchestration
5. Add document fetcher and MinIO storage integration
6. Build parser v1 for supported accounts documents
7. Implement rule-based risk engine and snapshot builder
8. Build public search and company page frontend

## Recommended first milestone
### Milestone 1: searchable public company page
Scope:
- search
- company overview
- filings
- officers
- charges
- basic freshness metadata

This should ship before deep financial parsing is perfect.

## Recommended second milestone
### Milestone 2: explainable financial intelligence
Scope:
- parser v1
- chartable financial facts
- derived metrics
- risk signal engine
- methodology page

## Recommended third milestone
### Milestone 3: retention loop
Scope:
- auth
- watchlists
- alerts
- scheduled refreshes

## Final recommendation
The best way to succeed with this in Cursor is to treat the product as a data platform with a polished frontend, not a frontend with some data behind it.

If you get the ingestion, period-based financial model, parser confidence, and snapshot assembly right, the rest of the product becomes much easier to build and much more credible.
