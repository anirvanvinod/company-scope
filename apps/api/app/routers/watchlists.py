"""
Authenticated user endpoints — current user profile and watchlist management.

All routes require a valid JWT (get_current_user dependency).
Mounted at /api/v1 via main.py.

  GET    /api/v1/me
  GET    /api/v1/watchlists
  POST   /api/v1/watchlists
  GET    /api/v1/watchlists/{watchlist_id}
  POST   /api/v1/watchlists/{watchlist_id}/items
  DELETE /api/v1/watchlists/{watchlist_id}/items/{company_number}
"""

from __future__ import annotations

import uuid
from typing import Annotated

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth import CurrentUserDep
from app.db.session import get_session
from app.queries.companies import get_company_by_number
from app.queries.users import (
    add_company_to_watchlist,
    create_watchlist,
    get_or_create_default_watchlist,
    get_watchlist_by_id,
    get_watchlist_items,
    get_watchlists_for_user,
    remove_company_from_watchlist,
)
from app.schemas.common import bad_request, not_found, ok, ok_list, unauthorized
from app.schemas.user import (
    AddItemRequest,
    CreateWatchlistRequest,
    UserOut,
    WatchlistItemOut,
    WatchlistOut,
)

router = APIRouter(tags=["user"])

SessionDep = Annotated[AsyncSession, Depends(get_session)]


# ---------------------------------------------------------------------------
# Current user
# ---------------------------------------------------------------------------


@router.get("/me")
async def get_me(current_user: CurrentUserDep) -> JSONResponse:
    """Return the profile of the authenticated user."""
    user_out = UserOut(
        id=current_user["id"],
        email=current_user["email"],
        display_name=current_user.get("display_name"),
        auth_provider=current_user["auth_provider"],
    )
    return JSONResponse(ok(user_out.model_dump(mode="json")))


# ---------------------------------------------------------------------------
# Watchlists — list + create
# ---------------------------------------------------------------------------


@router.get("/watchlists")
async def list_watchlists(
    current_user: CurrentUserDep,
    session: SessionDep,
) -> JSONResponse:
    """List all watchlists owned by the current user."""
    rows = await get_watchlists_for_user(session, current_user["id"])
    items = [
        WatchlistOut(
            id=r["id"],
            name=r["name"],
            description=r.get("description"),
            is_default=r["is_default"],
            item_count=r["item_count"],
            created_at=r.get("created_at"),
        ).model_dump(mode="json")
        for r in rows
    ]
    return JSONResponse(ok_list(items))


@router.post("/watchlists", status_code=201)
async def create_new_watchlist(
    body: CreateWatchlistRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> JSONResponse:
    """Create a new named watchlist for the current user."""
    wl = await create_watchlist(
        session,
        user_id=current_user["id"],
        name=body.name,
        description=body.description,
    )
    out = WatchlistOut(
        id=wl["id"],
        name=wl["name"],
        description=wl.get("description"),
        is_default=wl["is_default"],
        item_count=0,
    )
    return JSONResponse(ok(out.model_dump(mode="json")), status_code=201)


# ---------------------------------------------------------------------------
# Single watchlist + items
# ---------------------------------------------------------------------------


@router.get("/watchlists/{watchlist_id}")
async def get_watchlist(
    watchlist_id: uuid.UUID,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> JSONResponse:
    """Get a watchlist with its items. Returns 404 if not found or not owned."""
    wl = await get_watchlist_by_id(session, watchlist_id, current_user["id"])
    if not wl:
        return JSONResponse(
            not_found(f"Watchlist {watchlist_id} not found"), status_code=404
        )

    raw_items = await get_watchlist_items(session, watchlist_id)
    items_out = [
        WatchlistItemOut(
            company_number=r["company_number"],
            company_name=r["company_name"],
            company_status=r.get("company_status"),
            monitoring_status=r["monitoring_status"],
            added_at=r["created_at"],
        ).model_dump(mode="json")
        for r in raw_items
    ]

    wl_out = WatchlistOut(
        id=wl["id"],
        name=wl["name"],
        description=wl.get("description"),
        is_default=wl["is_default"],
        item_count=len(items_out),
        created_at=wl.get("created_at"),
    )
    return JSONResponse(
        ok({"watchlist": wl_out.model_dump(mode="json"), "items": items_out})
    )


@router.post("/watchlists/{watchlist_id}/items", status_code=201)
async def add_item(
    watchlist_id: uuid.UUID,
    body: AddItemRequest,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> JSONResponse:
    """
    Add a company to a watchlist.

    Returns 404 if the watchlist is not owned by the current user or if the
    company does not exist in the local database.
    """
    wl = await get_watchlist_by_id(session, watchlist_id, current_user["id"])
    if not wl:
        return JSONResponse(
            not_found(f"Watchlist {watchlist_id} not found"), status_code=404
        )

    company = await get_company_by_number(session, body.company_number)
    if not company:
        return JSONResponse(
            not_found(
                f"Company {body.company_number!r} not found in the local database. "
                "It may not have been ingested yet."
            ),
            status_code=404,
        )

    await add_company_to_watchlist(session, watchlist_id, company["id"])
    return JSONResponse(
        ok(
            {
                "watchlist_id": str(watchlist_id),
                "company_number": body.company_number,
            }
        ),
        status_code=201,
    )


@router.delete("/watchlists/{watchlist_id}/items/{company_number}")
async def remove_item(
    watchlist_id: uuid.UUID,
    company_number: str,
    current_user: CurrentUserDep,
    session: SessionDep,
) -> JSONResponse:
    """
    Remove a company from a watchlist.

    Returns 404 if the watchlist is not owned or the company is not in it.
    """
    wl = await get_watchlist_by_id(session, watchlist_id, current_user["id"])
    if not wl:
        return JSONResponse(
            not_found(f"Watchlist {watchlist_id} not found"), status_code=404
        )

    removed = await remove_company_from_watchlist(session, watchlist_id, company_number)
    if not removed:
        return JSONResponse(
            not_found(f"Company {company_number!r} is not in this watchlist"),
            status_code=404,
        )

    return JSONResponse(ok({"removed": True, "company_number": company_number}))
