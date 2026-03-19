"""
CompanyScope API — FastAPI application entry point.
"""

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.config import settings
import app.models  # noqa: F401 — registers all ORM models with Base.metadata at startup
from app.rate_limit import limiter
from app.routers.companies import router as companies_router
from app.routers.auth import router as auth_router
from app.routers.watchlists import router as watchlists_router

app = FastAPI(
    title="CompanyScope API",
    version="0.1.0",
    description="Explainable UK company intelligence API",
    # Disable interactive docs in production to reduce attack surface
    docs_url="/docs" if not settings.is_production else None,
    redoc_url="/redoc" if not settings.is_production else None,
)

# ---------------------------------------------------------------------------
# Rate limiter — attach to app.state so slowapi can find it
# ---------------------------------------------------------------------------

app.state.limiter = limiter


@app.exception_handler(RateLimitExceeded)
async def _rate_limit_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    """Return a 429 in the standard API error envelope."""
    return JSONResponse(
        {
            "data": None,
            "meta": {},
            "error": {
                "code": "rate_limited",
                "message": "Too many requests. Please slow down and try again.",
                "details": {},
            },
        },
        status_code=429,
    )

# ---------------------------------------------------------------------------
# CORS — allow the Next.js origin to make credentialled requests
# ---------------------------------------------------------------------------

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)

# ---------------------------------------------------------------------------
# Routers
# ---------------------------------------------------------------------------

app.include_router(companies_router, prefix="/api/v1")
app.include_router(auth_router, prefix="/api/v1")
app.include_router(watchlists_router, prefix="/api/v1")

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
# Root
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
