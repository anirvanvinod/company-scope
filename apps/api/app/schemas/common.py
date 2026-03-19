"""
Common response envelope types for the CompanyScope API.

Every endpoint returns one of:
  ApiResponse[T]       — single object
  ApiListResponse[T]   — paginated list

Error responses use the same envelope with data=null and error populated.
request_id is a randomly generated UUID per request for log correlation.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _req_id() -> str:
    return f"req_{uuid.uuid4().hex[:12]}"


# ---------------------------------------------------------------------------
# Envelope building helpers (used by route handlers)
# ---------------------------------------------------------------------------


def ok(data: Any, request_id: str | None = None) -> dict:
    """Wrap a data payload in the standard success envelope."""
    return {
        "data": data,
        "meta": {
            "request_id": request_id or _req_id(),
            "generated_at": _now_iso(),
        },
        "error": None,
    }


def ok_list(
    items: list,
    request_id: str | None = None,
    next_cursor: str | None = None,
    limit: int = 20,
) -> dict:
    """Wrap a list payload with pagination metadata."""
    return {
        "data": items,
        "meta": {
            "request_id": request_id or _req_id(),
            "generated_at": _now_iso(),
            "pagination": {
                "next_cursor": next_cursor,
                "limit": limit,
            },
        },
        "error": None,
    }


def not_found(message: str, request_id: str | None = None) -> dict:
    """Return a 404-shaped error envelope."""
    return {
        "data": None,
        "meta": {"request_id": request_id or _req_id()},
        "error": {
            "code": "not_found",
            "message": message,
            "details": {},
        },
    }


def unauthorized(message: str, request_id: str | None = None) -> dict:
    return {
        "data": None,
        "meta": {"request_id": request_id or _req_id()},
        "error": {
            "code": "unauthorized",
            "message": message,
            "details": {},
        },
    }


def bad_request(message: str, details: dict | None = None, request_id: str | None = None) -> dict:
    return {
        "data": None,
        "meta": {"request_id": request_id or _req_id()},
        "error": {
            "code": "bad_request",
            "message": message,
            "details": details or {},
        },
    }
