"""User-related Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field


# --- Request schemas ---

class UserRegisterRequest(BaseModel):
    """Registration request payload."""
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.]+$")
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = Field(None, max_length=50)


class UserLoginRequest(BaseModel):
    """Login request — supports username or email."""
    username_or_email: str
    password: str


class UserUpdateRequest(BaseModel):
    """Profile update request."""
    display_name: str | None = Field(None, max_length=50)
    avatar_id: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=140)


# --- Response schemas ---

class UserPublicResponse(BaseModel):
    """Public profile visible to other players."""
    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_id: str
    level: int
    games_played: int
    games_won: int
    win_rate: float
    favorite_category: str | None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMeResponse(UserPublicResponse):
    """Full profile for the authenticated user (includes private data)."""
    email: str | None
    phone: str | None
    bio: str | None
    xp: int
    coins: int
    gems: int
    is_active: bool
    last_login_at: datetime | None
    updated_at: datetime | None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token response after login/register."""
    access_token: str
    token_type: str = "bearer"
    user: UserMeResponse
