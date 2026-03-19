# CompanyScope — Local / Dev Runbook

## Prerequisites

| Tool | Minimum version | Install |
|---|---|---|
| Python | 3.12 | [python.org](https://www.python.org/) |
| Node.js | 20 | [nodejs.org](https://nodejs.org/) |
| pnpm | 9 | `npm i -g pnpm` |
| uv | 0.5+ | `pip install uv` or [docs.astral.sh/uv](https://docs.astral.sh/uv/) |
| Docker + Compose | v2 | [docs.docker.com](https://docs.docker.com/) |

---

## First-time setup

```bash
# 1. Clone and enter the repo
git clone <repo-url>
cd uk-companies-financial-analysis

# 2. Create your local .env file from the example
cp .env.example .env
# Edit .env — at minimum set CH_API_KEY and SECRET_KEY:
#   CH_API_KEY=<your Companies House API key>
#   SECRET_KEY=$(openssl rand -hex 32)

# 3. Install Python workspace dependencies (API + worker + shared packages)
uv sync --group dev

# 4. Install frontend dependencies
cd apps/web && pnpm install && cd ../..
```

---

## Starting services

### Option A — full Docker stack (recommended)

Starts PostgreSQL, Redis, MinIO, the API, the worker, and the Next.js web app.

```bash
docker compose up
```

On first run, run migrations before the API handles requests:

```bash
docker compose exec api uv run alembic -c apps/api/alembic.ini upgrade head
```

Service URLs:
| Service | URL |
|---|---|
| Next.js web app | http://localhost:3000 |
| FastAPI (docs) | http://localhost:8000/docs |
| FastAPI (health) | http://localhost:8000/internal/v1/health |
| MinIO console | http://localhost:9001 (user: `minioadmin` / pw: `minioadmin`) |

### Option B — infrastructure in Docker, services locally

Useful when iterating on API or frontend code without rebuilding Docker images.

```bash
# Start only the infrastructure services
docker compose up postgres redis minio minio-init

# In one terminal — run the API
cd apps/api
uv run uvicorn app.main:app --reload --port 8000

# In another terminal — run the frontend
cd apps/web
pnpm dev
```

The worker can be started similarly if needed:
```bash
cd apps/worker
uv run celery -A app.main:celery_app worker --loglevel=info
```

---

## Running database migrations

```bash
# Apply all pending migrations
cd apps/api
uv run alembic upgrade head

# Check current migration state
uv run alembic current

# Create a new migration (auto-generates from model diff)
uv run alembic revision --autogenerate -m "describe the change"
```

Migration files live in `apps/api/alembic/versions/`.

---

## Running tests

### API tests (no live database required)

```bash
cd apps/api
uv run pytest
```

Tests that require a live database are skipped automatically unless
`TEST_DATABASE_URL` is set:

```bash
# Run all tests including DB tests
TEST_DATABASE_URL=postgresql+asyncpg://companyscope:companyscope@localhost:5432/companyscope_test \
  uv run pytest
```

### CH client tests

```bash
cd packages/ch-client
uv run pytest
```

Or run from the repo root across all packages:

```bash
uv run pytest apps/api/tests apps/worker/tests packages/ch-client/tests
```

### Frontend type-check and lint

```bash
cd apps/web
pnpm type-check
pnpm lint
```

---

## Common issues

### `SECRET_KEY must be changed from the default value in production`

The API refuses to start with `SECRET_KEY=change-me-in-production` when
`ENVIRONMENT=production`. Generate a secure key:

```bash
openssl rand -hex 32
```

Set the result as `SECRET_KEY` in your `.env` or deployment environment.

### `TEST_DATABASE_URL not set — skipping database test`

This is informational, not a failure. DB-dependent tests are skipped when
the environment variable is absent. To run them, point at a Postgres instance:

```bash
# Using Docker Compose infrastructure
export TEST_DATABASE_URL=postgresql+asyncpg://companyscope:companyscope@localhost:5432/companyscope
```

Create the test database first if it doesn't exist:
```bash
docker compose exec postgres createdb -U companyscope companyscope
```

### Port already in use

```bash
# Find and kill the process using port 8000
lsof -ti :8000 | xargs kill -9
# Or change the port:
uv run uvicorn app.main:app --reload --port 8001
```

### MinIO bucket not created

The `minio-init` service creates the `companyscope-documents` bucket on first
`docker compose up`. If it failed, run it manually:

```bash
docker compose run --rm minio-init
```

### Alembic `can't locate revision identified by ...`

Your local DB is ahead of or behind the migration chain. Check the state:

```bash
uv run alembic history --verbose
uv run alembic current
```

To reset to the latest revision (destructive — dev only):
```bash
uv run alembic downgrade base && uv run alembic upgrade head
```

---

## Environment variables quick reference

See `.env.example` at the repo root for the full variable list with comments.

| Variable | Required in prod | Purpose |
|---|---|---|
| `DATABASE_URL` | yes | PostgreSQL connection string (asyncpg) |
| `REDIS_URL` | yes | Redis connection (Celery broker + rate limiter) |
| `SECRET_KEY` | yes | JWT signing secret — must not be the default |
| `CH_API_KEY` | yes | Companies House REST API key |
| `ENVIRONMENT` | yes | Set to `production` in prod; `development` locally |
| `API_INTERNAL_URL` | yes (Docker) | Server-side Next.js → API URL (Docker network name) |
| `NEXT_PUBLIC_API_URL` | yes | Browser → API URL (host-accessible) |
| `MINIO_*` | for workers | Object storage credentials and endpoint |
