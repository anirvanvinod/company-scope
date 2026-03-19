"""
JWT-based authentication utilities for CompanyScope.

Token format (HS256 JWT):
  sub   — str(user_id UUID)
  email — str
  exp   — UTC timestamp (30 days from issue)

Token transport:
  FastAPI reads from  Authorization: Bearer <token>  header first,
  then falls back to  Cookie: cs_session=<token>.

  The Next.js front end (server actions / server components) always sends
  the token as Authorization: Bearer so that CORS credentials are never
  needed for browser-direct calls.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any

import bcrypt
import jwt
from fastapi import Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.db.session import get_session

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ALGORITHM = "HS256"
_TOKEN_EXPIRE_DAYS = 30


# ---------------------------------------------------------------------------
# Password hashing
# ---------------------------------------------------------------------------


def hash_password(plain: str) -> str:
    """Return a bcrypt hash of the plain-text password."""
    return bcrypt.hashpw(plain.encode(), bcrypt.gensalt()).decode()


def verify_password(plain: str, hashed: str) -> bool:
    """Return True if plain matches the stored bcrypt hash."""
    try:
        return bcrypt.checkpw(plain.encode(), hashed.encode())
    except Exception:
        return False


# ---------------------------------------------------------------------------
# JWT encoding / decoding
# ---------------------------------------------------------------------------


def create_access_token(user_id: uuid.UUID, email: str) -> str:
    """Create a signed JWT for the given user."""
    exp = datetime.now(timezone.utc) + timedelta(days=_TOKEN_EXPIRE_DAYS)
    return jwt.encode(
        {"sub": str(user_id), "email": email, "exp": exp},
        settings.secret_key,
        algorithm=_ALGORITHM,
    )


def decode_access_token(token: str) -> dict[str, Any]:
    """
    Decode and verify a JWT.

    Raises ValueError on expiry, invalid signature, or malformed input.
    Returns the raw payload dict on success.
    """
    try:
        return jwt.decode(token, settings.secret_key, algorithms=[_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise ValueError("Token has expired")
    except jwt.InvalidTokenError as exc:
        raise ValueError(f"Invalid token: {exc}")


# ---------------------------------------------------------------------------
# FastAPI dependency
# ---------------------------------------------------------------------------


def _extract_token(request: Request) -> str | None:
    """Pull the JWT from Authorization: Bearer or cs_session cookie."""
    auth = request.headers.get("Authorization", "")
    if auth.startswith("Bearer "):
        return auth[7:]
    return request.cookies.get("cs_session") or None


async def get_current_user(
    request: Request,
    session: Annotated[AsyncSession, Depends(get_session)],
) -> dict[str, Any]:
    """
    Require an authenticated user.

    Reads the JWT, verifies it, fetches the user row.
    Raises HTTP 401 if the token is absent, expired, or the user is gone.
    """
    # Deferred import to avoid circular references at module load time
    from app.queries.users import get_user_by_id

    token = _extract_token(request)
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication required",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        payload = decode_access_token(token)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        )

    sub = payload.get("sub")
    if not sub:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad token")

    try:
        user_id = uuid.UUID(sub)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Bad token")

    user = await get_user_by_id(session, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
        )
    return user


# Convenience type alias for route function signatures
CurrentUserDep = Annotated[dict[str, Any], Depends(get_current_user)]
