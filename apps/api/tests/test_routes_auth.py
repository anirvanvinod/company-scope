"""
Tests for /api/v1/auth/* endpoints.

Uses async_client (unauthenticated) and patches the DB query functions
so no live database is needed.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_EXISTING_USER = {
    "id": uuid.UUID("bbbbbbbb-bbbb-bbbb-bbbb-bbbbbbbbbbbb"),
    "email": "existing@example.com",
    "display_name": None,
    "auth_provider": "password",
    # bcrypt hash of "password123"
    "password_hash": "$2b$12$placeholder_hash_for_tests",
}


# ---------------------------------------------------------------------------
# Register
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_register_returns_201_and_token(async_client):
    with (
        patch(
            "app.routers.auth.get_user_by_email",
            new_callable=AsyncMock,
            return_value=None,  # email not taken
        ),
        patch(
            "app.routers.auth.create_user",
            new_callable=AsyncMock,
            return_value={
                "id": uuid.uuid4(),
                "email": "new@example.com",
                "display_name": None,
                "auth_provider": "password",
            },
        ),
        patch(
            "app.routers.auth.create_watchlist",
            new_callable=AsyncMock,
        ),
    ):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "new@example.com", "password": "securepassword"},
        )

    assert resp.status_code == 201
    body = resp.json()
    assert body["error"] is None
    assert "access_token" in body["data"]
    assert body["data"]["user"]["email"] == "new@example.com"


@pytest.mark.asyncio
async def test_register_conflict_if_email_taken(async_client):
    with patch(
        "app.routers.auth.get_user_by_email",
        new_callable=AsyncMock,
        return_value=_EXISTING_USER,
    ):
        resp = await async_client.post(
            "/api/v1/auth/register",
            json={"email": "existing@example.com", "password": "securepassword"},
        )

    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "bad_request"


@pytest.mark.asyncio
async def test_register_rejects_short_password(async_client):
    resp = await async_client.post(
        "/api/v1/auth/register",
        json={"email": "short@example.com", "password": "1234"},
    )
    assert resp.status_code == 422  # Pydantic validation


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_login_returns_200_and_token(async_client):
    import bcrypt

    real_hash = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode()
    user_with_hash = {**_EXISTING_USER, "password_hash": real_hash}

    with patch(
        "app.routers.auth.get_user_by_email",
        new_callable=AsyncMock,
        return_value=user_with_hash,
    ):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "existing@example.com", "password": "correctpassword"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert "access_token" in body["data"]


@pytest.mark.asyncio
async def test_login_wrong_password_returns_401(async_client):
    import bcrypt

    real_hash = bcrypt.hashpw(b"correctpassword", bcrypt.gensalt()).decode()
    user_with_hash = {**_EXISTING_USER, "password_hash": real_hash}

    with patch(
        "app.routers.auth.get_user_by_email",
        new_callable=AsyncMock,
        return_value=user_with_hash,
    ):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "existing@example.com", "password": "wrongpassword"},
        )

    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.asyncio
async def test_login_unknown_email_returns_401(async_client):
    with patch(
        "app.routers.auth.get_user_by_email",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await async_client.post(
            "/api/v1/auth/login",
            json={"email": "nobody@example.com", "password": "somepassword"},
        )

    assert resp.status_code == 401


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_logout_returns_200(async_client):
    resp = await async_client.post("/api/v1/auth/logout")
    assert resp.status_code == 200
    assert resp.json()["data"]["logged_out"] is True


# ---------------------------------------------------------------------------
# /me endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_me_requires_auth(async_client):
    """Calling /me without a token must return 401."""
    resp = await async_client.get("/api/v1/me")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_me_returns_user_with_valid_token(async_client):
    """A valid JWT should cause /me to return the user profile."""
    import uuid as _uuid
    from app.auth import create_access_token

    test_id = _uuid.UUID("aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa")
    test_user = {
        "id": test_id,
        "email": "test@example.com",
        "display_name": None,
        "auth_provider": "password",
    }
    token = create_access_token(test_id, "test@example.com")

    with patch(
        "app.auth.get_user_by_id",
        new_callable=AsyncMock,
        return_value=test_user,
    ):
        resp = await async_client.get(
            "/api/v1/me",
            headers={"Authorization": f"Bearer {token}"},
        )

    assert resp.status_code == 200
    body = resp.json()
    assert body["data"]["email"] == "test@example.com"


@pytest.mark.asyncio
async def test_me_expired_token_returns_401(async_client):
    """An expired token must be rejected."""
    from datetime import datetime, timedelta, timezone

    import jwt

    from app.config import settings

    expired_token = jwt.encode(
        {
            "sub": str(uuid.uuid4()),
            "email": "test@example.com",
            "exp": datetime.now(timezone.utc) - timedelta(days=1),
        },
        settings.secret_key,
        algorithm="HS256",
    )

    resp = await async_client.get(
        "/api/v1/me",
        headers={"Authorization": f"Bearer {expired_token}"},
    )
    assert resp.status_code == 401
