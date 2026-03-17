# CompanyScope

Explainable UK company intelligence platform built on Companies House public data.

## What it does

- Search UK companies by name or company number
- View filing-derived financial trends with confidence indicators
- Inspect officers, PSCs, charges, and insolvency records
- Review transparent, rule-based risk signals linked to source filings

This product is informational only. It is not investment advice, legal advice, or a credit score.

## Stack

| Layer | Technology |
|---|---|
| Frontend | Next.js 15, TypeScript, Tailwind CSS, shadcn/ui |
| API | FastAPI, Pydantic v2, SQLAlchemy 2.x |
| Workers | Celery + Redis |
| Database | PostgreSQL 16 |
| Object storage | MinIO |
| Monitoring | Prometheus, Grafana, Loki |

## Local development

### Prerequisites

- [uv](https://docs.astral.sh/uv/) (Python package manager)
- [pnpm](https://pnpm.io/) (Node package manager)
- [Docker](https://www.docker.com/) and Docker Compose

### Setup

```bash
# 1. Copy env file and fill in your Companies House API key
cp .env.example .env

# 2. Start the full stack
docker compose up

# Services:
#   web    → http://localhost:3000
#   api    → http://localhost:8000
#   minio  → http://localhost:9001  (console)
#   postgres → localhost:5432
#   redis  → localhost:6379
```

### Running services individually

```bash
# API
cd apps/api
uv run uvicorn app.main:app --reload

# Worker
cd apps/worker
uv run celery -A app.main:celery_app worker --loglevel=info

# Web
cd apps/web
pnpm dev
```

### Health check

```bash
curl http://localhost:8000/internal/v1/health
```

## Project structure

```
apps/
  web/      Next.js frontend
  api/      FastAPI backend
  worker/   Celery background workers
packages/
  schemas/  Shared TypeScript types and generated API types
  ui/       Shared UI components (later)
  config/   Shared configuration (later)
infra/
  docker/   Dockerfiles
  opentofu/ Infrastructure as code (later phases)
docs/       Architecture, schema, API spec, and methodology
```

## Documentation

| Document | Purpose |
|---|---|
| `docs/01-system-architecture.md` | Architecture overview and service boundaries |
| `docs/02-database-schema.md` | PostgreSQL schema |
| `docs/03-api-spec.md` | REST API contract |
| `docs/04-cursor-build-plan.md` | Phased build plan |
| `docs/05-parser-design.md` | Financial document parser design |
| `docs/06-methodology.md` | How signals and metrics are calculated |
| `docs/07-frontend-wireframes.md` | UI wireframes |
| `docs/08-testing-strategy.md` | Testing approach |
| `docs/decisions/` | Architecture decision records |

## Data discipline

- Missing values are never silently converted to zero
- Every metric and signal links back to a source filing
- Parser version and methodology version are recorded on all derived artefacts
