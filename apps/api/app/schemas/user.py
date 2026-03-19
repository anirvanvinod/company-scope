"""
Pydantic schemas for auth and watchlist API endpoints.

Request bodies: RegisterRequest, LoginRequest, CreateWatchlistRequest, AddItemRequest
Response shapes: UserOut, WatchlistOut, WatchlistItemOut, AuthOut
"""

from __future__ import annotations

import uuid
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, EmailStr, Field


# ---------------------------------------------------------------------------
# Auth request / response
# ---------------------------------------------------------------------------


class RegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: Optional[str] = Field(default=None, max_length=128)


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=1, max_length=128)


class UserOut(BaseModel):
    id: uuid.UUID
    email: str
    display_name: Optional[str]
    auth_provider: str


class AuthOut(BaseModel):
    """Response body for register and login."""
    access_token: str
    token_type: str = "bearer"
    user: UserOut


# ---------------------------------------------------------------------------
# Watchlist request / response
# ---------------------------------------------------------------------------


class CreateWatchlistRequest(BaseModel):
    name: str = Field(min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)


class AddItemRequest(BaseModel):
    company_number: str = Field(min_length=1, max_length=16)


class WatchlistItemOut(BaseModel):
    company_number: str
    company_name: str
    company_status: Optional[str]
    monitoring_status: str
    added_at: datetime


class WatchlistOut(BaseModel):
    id: uuid.UUID
    name: str
    description: Optional[str]
    is_default: bool
    item_count: int
    created_at: Optional[datetime] = None
