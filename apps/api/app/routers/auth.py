"""
Authentication endpoints.

Mounted at /api/v1/auth/* via main.py.

  POST /api/v1/auth/register   — create account, return JWT
  POST /api/v1/auth/login      — verify credentials, return JWT
  POST /api/v1/auth/logout     — no-op (cookie is managed by the Next.js front end)

The JWT is returned in the response body as AuthOut.access_token.
The Next.js Server Action that calls these endpoints is responsible for
setting / clearing the cs_session HTTP-only cookie in the browser.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.rate_limit import limiter

from app.auth import (
    CurrentUserDep,
    create_access_token,
    hash_password,
    verify_password,
)
from app.db.session import get_session
from app.queries.users import (
    create_user,
    create_watchlist,
    get_user_by_email,
)
from app.schemas.common import bad_request, ok, unauthorized
from app.schemas.user import AuthOut, LoginRequest, RegisterRequest, UserOut

router = APIRouter(prefix="/auth", tags=["auth"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@router.post("/register", status_code=201)
@limiter.limit("5/minute")
async def register(request: Request, body: RegisterRequest, session: SessionDep) -> JSONResponse:
    """
    Create a new user account.

    Returns HTTP 409 if the email is already registered.
    Auto-creates a default "My companies" watchlist for the new user.
    """
    existing = await get_user_by_email(session, body.email)
    if existing:
        return JSONResponse(
            bad_request("Email already registered", {"field": "email"}),
            status_code=409,
        )

    user = await create_user(
        session,
        email=body.email,
        password_hash=hash_password(body.password),
        display_name=body.display_name,
    )

    # Auto-create the default watchlist so the front end always has one to target
    await create_watchlist(session, user["id"], "My companies", is_default=True)

    token = create_access_token(user["id"], user["email"])
    payload = AuthOut(
        access_token=token,
        user=UserOut(
            id=user["id"],
            email=user["email"],
            display_name=user["display_name"],
            auth_provider=user["auth_provider"],
        ),
    )
    return JSONResponse(ok(payload.model_dump(mode="json")), status_code=201)


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@router.post("/login")
@limiter.limit("10/minute")
async def login(request: Request, body: LoginRequest, session: SessionDep) -> JSONResponse:
    """
    Verify credentials and return a JWT.

    Returns HTTP 401 for unknown email or wrong password (same message
    to avoid user enumeration).
    """
    user = await get_user_by_email(session, body.email)
    if not user or not user.get("password_hash"):
        return JSONResponse(
            unauthorized("Invalid email or password"),
            status_code=401,
        )

    if not verify_password(body.password, user["password_hash"]):
        return JSONResponse(
            unauthorized("Invalid email or password"),
            status_code=401,
        )

    token = create_access_token(user["id"], user["email"])
    payload = AuthOut(
        access_token=token,
        user=UserOut(
            id=user["id"],
            email=user["email"],
            display_name=user.get("display_name"),
            auth_provider=user["auth_provider"],
        ),
    )
    return JSONResponse(ok(payload.model_dump(mode="json")))


# ---------------------------------------------------------------------------
# Logout (informational — the real cleanup is cookie deletion in Next.js)
# ---------------------------------------------------------------------------


@router.post("/logout")
async def logout() -> JSONResponse:
    """
    Acknowledge a logout request.

    The actual session termination (cookie deletion) is performed by the
    Next.js Server Action that calls this endpoint.
    """
    return JSONResponse(ok({"logged_out": True}))


# ---------------------------------------------------------------------------
# Current user — /api/v1/me (logically part of auth, mounted in watchlists router)
# ---------------------------------------------------------------------------
# Note: /me is defined in watchlists.py (same file as user-scoped endpoints)
# to keep route mounting simple. See watchlists.py for that handler.
