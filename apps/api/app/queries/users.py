"""
DB query functions for users, watchlists, and watchlist items.

Uses raw SQL via sa.text() consistent with the companies query module.
All writes commit immediately; callers are responsible for wrapping in
transactions if broader atomicity is needed.
"""

from __future__ import annotations

import uuid
from typing import Any

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession


# ---------------------------------------------------------------------------
# Users
# ---------------------------------------------------------------------------


async def get_user_by_email(
    session: AsyncSession,
    email: str,
) -> dict[str, Any] | None:
    result = await session.execute(
        sa.text(
            """
            SELECT id, email, display_name, auth_provider, auth_subject, password_hash
            FROM   users
            WHERE  email = :email
            """
        ),
        {"email": email},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def get_user_by_id(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any] | None:
    result = await session.execute(
        sa.text(
            """
            SELECT id, email, display_name, auth_provider
            FROM   users
            WHERE  id = :id
            """
        ),
        {"id": user_id},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def create_user(
    session: AsyncSession,
    email: str,
    password_hash: str,
    display_name: str | None = None,
) -> dict[str, Any]:
    """Insert a new user row and return id + email."""
    user_id = uuid.uuid4()
    await session.execute(
        sa.text(
            """
            INSERT INTO users
                (id, email, display_name, auth_provider, auth_subject,
                 password_hash, created_at, updated_at)
            VALUES
                (:id, :email, :display_name, 'password', NULL,
                 :password_hash, now(), now())
            """
        ),
        {
            "id": user_id,
            "email": email,
            "display_name": display_name,
            "password_hash": password_hash,
        },
    )
    await session.commit()
    return {
        "id": user_id,
        "email": email,
        "display_name": display_name,
        "auth_provider": "password",
    }


# ---------------------------------------------------------------------------
# Watchlists
# ---------------------------------------------------------------------------


async def get_watchlists_for_user(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> list[dict[str, Any]]:
    result = await session.execute(
        sa.text(
            """
            SELECT  w.id,
                    w.name,
                    w.description,
                    w.is_default,
                    w.created_at,
                    count(wi.id)::int AS item_count
            FROM    watchlists w
            LEFT    JOIN watchlist_items wi ON wi.watchlist_id = w.id
            WHERE   w.user_id = :user_id
            GROUP   BY w.id
            ORDER   BY w.is_default DESC, w.created_at ASC
            """
        ),
        {"user_id": user_id},
    )
    return [dict(r) for r in result.mappings()]


async def get_watchlist_by_id(
    session: AsyncSession,
    watchlist_id: uuid.UUID,
    user_id: uuid.UUID,
) -> dict[str, Any] | None:
    """Return watchlist only if it belongs to user_id (ownership check)."""
    result = await session.execute(
        sa.text(
            """
            SELECT id, name, description, is_default, created_at
            FROM   watchlists
            WHERE  id = :id AND user_id = :user_id
            """
        ),
        {"id": watchlist_id, "user_id": user_id},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None


async def create_watchlist(
    session: AsyncSession,
    user_id: uuid.UUID,
    name: str,
    description: str | None = None,
    is_default: bool = False,
) -> dict[str, Any]:
    wl_id = uuid.uuid4()
    await session.execute(
        sa.text(
            """
            INSERT INTO watchlists
                (id, user_id, name, description, is_default, created_at, updated_at)
            VALUES
                (:id, :user_id, :name, :description, :is_default, now(), now())
            """
        ),
        {
            "id": wl_id,
            "user_id": user_id,
            "name": name,
            "description": description,
            "is_default": is_default,
        },
    )
    await session.commit()
    return {
        "id": wl_id,
        "name": name,
        "description": description,
        "is_default": is_default,
        "item_count": 0,
    }


async def get_or_create_default_watchlist(
    session: AsyncSession,
    user_id: uuid.UUID,
) -> dict[str, Any]:
    """Return the user's default watchlist, creating it if absent."""
    result = await session.execute(
        sa.text(
            """
            SELECT id, name, description, is_default, created_at
            FROM   watchlists
            WHERE  user_id = :user_id AND is_default = true
            LIMIT  1
            """
        ),
        {"user_id": user_id},
    )
    row = result.mappings().one_or_none()
    if row:
        return dict(row)
    return await create_watchlist(
        session, user_id, "My companies", is_default=True
    )


# ---------------------------------------------------------------------------
# Watchlist items
# ---------------------------------------------------------------------------


async def get_watchlist_items(
    session: AsyncSession,
    watchlist_id: uuid.UUID,
) -> list[dict[str, Any]]:
    result = await session.execute(
        sa.text(
            """
            SELECT  wi.id,
                    wi.monitoring_status,
                    wi.created_at,
                    c.company_number,
                    c.company_name,
                    c.company_status
            FROM    watchlist_items wi
            JOIN    companies c ON c.id = wi.company_id
            WHERE   wi.watchlist_id = :watchlist_id
            ORDER   BY wi.created_at DESC
            """
        ),
        {"watchlist_id": watchlist_id},
    )
    return [dict(r) for r in result.mappings()]


async def add_company_to_watchlist(
    session: AsyncSession,
    watchlist_id: uuid.UUID,
    company_id: uuid.UUID,
) -> None:
    """Insert watchlist item, silently ignore if already present (ON CONFLICT DO NOTHING)."""
    item_id = uuid.uuid4()
    await session.execute(
        sa.text(
            """
            INSERT INTO watchlist_items
                (id, watchlist_id, company_id, monitoring_status, created_at)
            VALUES
                (:id, :watchlist_id, :company_id, 'active', now())
            ON CONFLICT (watchlist_id, company_id) DO NOTHING
            """
        ),
        {"id": item_id, "watchlist_id": watchlist_id, "company_id": company_id},
    )
    await session.commit()


async def remove_company_from_watchlist(
    session: AsyncSession,
    watchlist_id: uuid.UUID,
    company_number: str,
) -> bool:
    """Delete the watchlist item. Returns True if a row was removed."""
    result = await session.execute(
        sa.text(
            """
            DELETE FROM watchlist_items
            WHERE  watchlist_id = :watchlist_id
            AND    company_id = (
                SELECT id FROM companies WHERE company_number = :cn
            )
            """
        ),
        {"watchlist_id": watchlist_id, "cn": company_number},
    )
    await session.commit()
    return (result.rowcount or 0) > 0


async def get_company_watch_state(
    session: AsyncSession,
    user_id: uuid.UUID,
    company_number: str,
) -> dict[str, Any] | None:
    """
    Return the first watchlist_id that this user has the company in, or None.
    Used to determine the initial watched state on company pages.
    """
    result = await session.execute(
        sa.text(
            """
            SELECT  wi.watchlist_id,
                    w.is_default
            FROM    watchlist_items wi
            JOIN    watchlists w ON w.id = wi.watchlist_id
            JOIN    companies  c ON c.id = wi.company_id
            WHERE   w.user_id       = :user_id
            AND     c.company_number = :cn
            LIMIT   1
            """
        ),
        {"user_id": user_id, "cn": company_number},
    )
    row = result.mappings().one_or_none()
    return dict(row) if row else None
