# CLAUDE.md

## Project
CompanyScope

An explainable UK company intelligence platform built primarily on top of Companies House public data.

## Read these documents first
1. `docs/01-system-architecture.md`
2. `docs/02-database-schema.md`
3. `docs/03-api-spec.md`
4. `docs/04-cursor-build-plan.md`
5. `docs/05-parser-design.md`
6. `docs/06-methodology.md`
7. `docs/07-frontend-wireframes.md`
8. `docs/08-testing-strategy.md`

## Product intent
Build a public-data intelligence product that helps users evaluate UK companies using:
- company identity and status
- filing history
- officers and PSCs
- charges and insolvency context
- filing-derived financial trends
- transparent rules-based signals
- confidence and freshness indicators

## Non-goals
Do not position the product as:
- investment advice
- legal advice
- accounting advice
- a regulated credit score
- a guaranteed predictor of company performance

Avoid language that implies certainty beyond the evidence.

## Preferred stack
- Frontend: Next.js + TypeScript + Tailwind + shadcn/ui
- Backend: FastAPI
- Workers: Celery or Dramatiq
- Database: PostgreSQL
- Cache / queue: Redis
- Storage: MinIO
- Monitoring: Prometheus + Grafana + Loki

## Architecture summary
- The browser never calls Companies House directly
- The API service owns upstream integration
- The worker service handles ingestion, document fetching, parsing, and scheduled refreshes
- Financial facts are stored as period-based, provenance-linked records
- Signals must be explainable and methodology-linked

## Coding expectations
- Keep modules small and clear
- Use strict TypeScript
- Use Pydantic and SQLAlchemy in Python services
- Use Decimal for monetary values
- Validate all external data
- Keep raw facts, derived metrics, and signals conceptually separate

## Data discipline
- Never silently convert missing values to zero
- Never fabricate fields not supported by evidence
- Preserve source links for all important metrics and signals
- Preserve parser version and methodology version where relevant

## Implementation order
1. Scaffold monorepo structure
2. Set up web app, API service, worker service
3. Set up Postgres, Redis, and MinIO in local Docker Compose
4. Implement shared schemas and config
5. Implement company search and company profile aggregation
6. Implement filings, officers, PSC, charges, and insolvency ingestion
7. Implement document fetch and parser pipeline
8. Implement financial facts persistence
9. Implement rule-based signals
10. Implement watchlist and auth
11. Implement testing and observability

## UI priorities
- Search-first landing page
- Strong company overview page
- Financials tab with charts and confidence
- Filing timeline with source links
- Methodology page for trust

## Quality gates
Before considering a task complete:
- code should align with the docs
- tests should be added or updated where behaviour changed
- no secret should be exposed client-side
- API responses should remain consistent with `docs/03-api-spec.md`

## How to behave while coding
- Prefer incremental, reviewable changes
- State assumptions briefly in code comments or commit messages where needed
- If the docs and existing code conflict, favour the docs unless a strong technical reason requires an update
- If an API or schema change is needed, update the corresponding docs too
