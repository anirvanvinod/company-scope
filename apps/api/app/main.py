"""
CompanyScope API — FastAPI application entry point.

Phase 0: health and readiness endpoints only.
Business logic, Companies House integration, and routers are added in later phases.
"""

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from app.config import settings
import app.models  # noqa: F401 — registers all ORM models with Base.metadata at startup

app = FastAPI(
    title="CompanyScope API",
    version="0.1.0",
    description="Explainable UK company intelligence API",
    # Disable interactive docs in production to reduce attack surface
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)


# ---------------------------------------------------------------------------
# Internal health endpoints (not part of the public API surface)
# See docs/03-api-spec.md §24 for the full internal endpoint list
# ---------------------------------------------------------------------------


@app.get("/internal/v1/health", include_in_schema=False)
async def health() -> JSONResponse:
    """Liveness probe — confirms the process is running."""
    return JSONResponse({"status": "ok", "service": "api"})


@app.get("/internal/v1/ready", include_in_schema=False)
async def ready() -> JSONResponse:
    """
    Readiness probe — will check DB and Redis connectivity in Phase 1.

    Phase 0: returns ready immediately (no dependencies wired yet).
    """
    return JSONResponse({"status": "ready", "service": "api"})


# ---------------------------------------------------------------------------
# Phase 0 root redirect — placeholder until the public API is wired up
# ---------------------------------------------------------------------------


@app.get("/", include_in_schema=False)
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "service": "CompanyScope API",
            "version": "0.1.0",
            "docs": "/docs",
            "health": "/internal/v1/health",
        }
    )
