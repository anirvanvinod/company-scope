"""
Tests for authenticated watchlist endpoints.

Uses auth_client, which bypasses JWT verification by overriding
get_current_user to return the mock user from conftest.

All DB query functions are patched so no live DB is needed.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_WL_ID = uuid.UUID("cccccccc-cccc-cccc-cccc-cccccccccccc")
_COMPANY_ID = uuid.UUID("dddddddd-dddd-dddd-dddd-dddddddddddd")

_WATCHLIST_ROW = {
    "id": _WL_ID,
    "name": "My companies",
    "description": None,
    "is_default": True,
    "item_count": 1,
    "created_at": datetime(2026, 1, 1, tzinfo=timezone.utc),
}

_ITEM_ROW = {
    "company_number": "12345678",
    "company_name": "ACME LTD",
    "company_status": "active",
    "monitoring_status": "active",
    "created_at": datetime(2026, 1, 2, tzinfo=timezone.utc),
}

_COMPANY_ROW = {
    "id": _COMPANY_ID,
    "company_number": "12345678",
    "company_name": "ACME LTD",
}


# ---------------------------------------------------------------------------
# /api/v1/watchlists — list
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_watchlists_requires_auth(async_client):
    resp = await async_client.get("/api/v1/watchlists")
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_list_watchlists_returns_user_lists(auth_client):
    with patch(
        "app.routers.watchlists.get_watchlists_for_user",
        new_callable=AsyncMock,
        return_value=[_WATCHLIST_ROW],
    ):
        resp = await auth_client.get("/api/v1/watchlists")

    assert resp.status_code == 200
    body = resp.json()
    assert body["error"] is None
    assert len(body["data"]) == 1
    assert body["data"][0]["name"] == "My companies"
    assert body["data"][0]["is_default"] is True


@pytest.mark.asyncio
async def test_list_watchlists_empty(auth_client):
    with patch(
        "app.routers.watchlists.get_watchlists_for_user",
        new_callable=AsyncMock,
        return_value=[],
    ):
        resp = await auth_client.get("/api/v1/watchlists")

    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------------------------------------------------------------------------
# POST /api/v1/watchlists — create
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_watchlist(auth_client):
    new_wl = {
        "id": uuid.uuid4(),
        "name": "Competitors",
        "description": "Industry peers",
        "is_default": False,
        "item_count": 0,
    }
    with patch(
        "app.routers.watchlists.create_watchlist",
        new_callable=AsyncMock,
        return_value=new_wl,
    ):
        resp = await auth_client.post(
            "/api/v1/watchlists",
            json={"name": "Competitors", "description": "Industry peers"},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["name"] == "Competitors"


@pytest.mark.asyncio
async def test_create_watchlist_rejects_empty_name(auth_client):
    resp = await auth_client.post("/api/v1/watchlists", json={"name": ""})
    assert resp.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/watchlists/{id} — single watchlist with items
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_watchlist_with_items(auth_client):
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=_WATCHLIST_ROW,
        ),
        patch(
            "app.routers.watchlists.get_watchlist_items",
            new_callable=AsyncMock,
            return_value=[_ITEM_ROW],
        ),
    ):
        resp = await auth_client.get(f"/api/v1/watchlists/{_WL_ID}")

    assert resp.status_code == 200
    body = resp.json()["data"]
    assert body["watchlist"]["name"] == "My companies"
    assert len(body["items"]) == 1
    assert body["items"][0]["company_number"] == "12345678"


@pytest.mark.asyncio
async def test_get_watchlist_not_owned_returns_404(auth_client):
    with patch(
        "app.routers.watchlists.get_watchlist_by_id",
        new_callable=AsyncMock,
        return_value=None,  # not found / not owned
    ):
        resp = await auth_client.get(f"/api/v1/watchlists/{_WL_ID}")

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# POST /api/v1/watchlists/{id}/items — add company
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_add_company_to_watchlist(auth_client):
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=_WATCHLIST_ROW,
        ),
        patch(
            "app.routers.watchlists.get_company_by_number",
            new_callable=AsyncMock,
            return_value=_COMPANY_ROW,
        ),
        patch(
            "app.routers.watchlists.add_company_to_watchlist",
            new_callable=AsyncMock,
        ),
    ):
        resp = await auth_client.post(
            f"/api/v1/watchlists/{_WL_ID}/items",
            json={"company_number": "12345678"},
        )

    assert resp.status_code == 201
    assert resp.json()["data"]["company_number"] == "12345678"


@pytest.mark.asyncio
async def test_add_company_not_in_db_returns_404(auth_client):
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=_WATCHLIST_ROW,
        ),
        patch(
            "app.routers.watchlists.get_company_by_number",
            new_callable=AsyncMock,
            return_value=None,  # company not ingested yet
        ),
    ):
        resp = await auth_client.post(
            f"/api/v1/watchlists/{_WL_ID}/items",
            json={"company_number": "99999999"},
        )

    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_add_company_wrong_watchlist_returns_404(auth_client):
    with patch(
        "app.routers.watchlists.get_watchlist_by_id",
        new_callable=AsyncMock,
        return_value=None,
    ):
        resp = await auth_client.post(
            f"/api/v1/watchlists/{_WL_ID}/items",
            json={"company_number": "12345678"},
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/watchlists/{id}/items/{company_number} — remove company
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_remove_company_from_watchlist(auth_client):
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=_WATCHLIST_ROW,
        ),
        patch(
            "app.routers.watchlists.remove_company_from_watchlist",
            new_callable=AsyncMock,
            return_value=True,
        ),
    ):
        resp = await auth_client.delete(
            f"/api/v1/watchlists/{_WL_ID}/items/12345678"
        )

    assert resp.status_code == 200
    assert resp.json()["data"]["removed"] is True


@pytest.mark.asyncio
async def test_remove_company_not_in_watchlist_returns_404(auth_client):
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=_WATCHLIST_ROW,
        ),
        patch(
            "app.routers.watchlists.remove_company_from_watchlist",
            new_callable=AsyncMock,
            return_value=False,  # rowcount = 0
        ),
    ):
        resp = await auth_client.delete(
            f"/api/v1/watchlists/{_WL_ID}/items/99999999"
        )

    assert resp.status_code == 404


# ---------------------------------------------------------------------------
# Ownership — cannot access another user's watchlist
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_cannot_access_other_users_watchlist_items(auth_client):
    """
    get_watchlist_by_id enforces user_id; returning None simulates the
    row not existing for this user (ownership failure).
    """
    other_wl_id = uuid.uuid4()
    with (
        patch(
            "app.routers.watchlists.get_watchlist_by_id",
            new_callable=AsyncMock,
            return_value=None,
        ),
        patch(
            "app.routers.watchlists.get_watchlist_items",
            new_callable=AsyncMock,
        ) as mock_items,
    ):
        resp = await auth_client.get(f"/api/v1/watchlists/{other_wl_id}")

    assert resp.status_code == 404
    mock_items.assert_not_called()
