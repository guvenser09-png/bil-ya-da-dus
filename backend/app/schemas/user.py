"""User-related Pydantic schemas for request/response validation."""

import uuid
from datetime import datetime

from pydantic import BaseModel, EmailStr, Field, field_validator


# --- Request schemas ---

class UserRegisterRequest(BaseModel):
    """Registration request payload."""
    username: str = Field(..., min_length=3, max_length=30, pattern=r"^[a-zA-Z0-9_.]+$")
    email: str | None = Field(None, max_length=255)
    phone: str | None = Field(None, max_length=20)
    password: str = Field(..., min_length=6, max_length=128)
    display_name: str | None = Field(None, max_length=50)

    @field_validator("password")
    @classmethod
    def password_strength(cls, v: str) -> str:
        """Basic password strength check."""
        if len(v) < 6:
            raise ValueError("Şifre en az 6 karakter olmalı.")
        if v.isdigit():
            raise ValueError("Şifre sadece rakamlardan oluşamaz.")
        return v


class UserLoginRequest(BaseModel):
    """Login request — supports username or email."""
    username_or_email: str
    password: str


class UserUpdateRequest(BaseModel):
    """Profile update request."""
    display_name: str | None = Field(None, max_length=50)
    avatar_id: str | None = Field(None, max_length=100)
    bio: str | None = Field(None, max_length=140)
    interest_tags: list[str] | None = Field(None, max_length=5)

    @field_validator("interest_tags")
    @classmethod
    def validate_tags(cls, v: list[str] | None) -> list[str] | None:
        """Validate interest tags: max 5, each max 30 chars."""
        if v is None:
            return v
        if len(v) > 5:
            raise ValueError("En fazla 5 ilgi alanı etiketi eklenebilir.")
        for tag in v:
            if len(tag) > 30:
                raise ValueError(f"Etiket '{tag}' çok uzun (max 30 karakter).")
        return [tag.strip().lower() for tag in v]


class PasswordChangeRequest(BaseModel):
    """Password change for logged-in user."""
    current_password: str
    new_password: str = Field(..., min_length=6, max_length=128)

    @field_validator("new_password")
    @classmethod
    def new_password_strength(cls, v: str) -> str:
        if v.isdigit():
            raise ValueError("Yeni şifre sadece rakamlardan oluşamaz.")
        return v


class PasswordResetRequest(BaseModel):
    """Request password reset via email."""
    email: str


class PasswordResetConfirm(BaseModel):
    """Confirm password reset with token."""
    token: str
    new_password: str = Field(..., min_length=6, max_length=128)


class RefreshTokenRequest(BaseModel):
    """Refresh access token using refresh token."""
    refresh_token: str


class UserSearchRequest(BaseModel):
    """Search for users by username."""
    query: str = Field(..., min_length=2, max_length=30)
    limit: int = Field(10, ge=1, le=50)


# --- Response schemas ---

class UserPublicResponse(BaseModel):
    """Public profile visible to other players."""
    id: uuid.UUID
    username: str
    display_name: str | None
    avatar_id: str
    level: int
    season_level: int = 1
    games_played: int
    games_won: int
    win_rate: float
    total_score: int = 0
    best_streak: int = 0
    favorite_category: str | None
    interest_tags: list[str] | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class UserMeResponse(UserPublicResponse):
    """Full profile for the authenticated user (includes private data)."""
    email: str | None
    phone: str | None
    bio: str | None
    xp: int
    coins: int
    total_correct_answers: int = 0
    total_questions_answered: int = 0
    is_active: bool
    is_verified: bool = False
    # Misafir hesap mı? (claim ile kalıcılaşınca False olur)
    is_guest: bool = False
    last_login_at: datetime | None
    updated_at: datetime | None
    # Tutundurma + kozmetik
    daily_streak: int = 0
    equipped_frame: str | None = None
    equipped_name_color: str | None = None
    equipped_effect: str | None = None
    # Monetizasyon durumu (pay-to-win YOK)
    is_premium: bool = False
    premium_until: datetime | None = None
    has_battle_pass: bool = False
    starter_pack_purchased: bool = False

    model_config = {"from_attributes": True}


class UserStatsResponse(BaseModel):
    """Detailed player statistics."""
    games_played: int
    games_won: int
    win_rate: float
    total_score: int
    best_streak: int
    total_correct_answers: int
    total_questions_answered: int
    accuracy_rate: float
    favorite_category: str | None
    level: int
    xp: int
    best_rank: int | None = None

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    """JWT token response after login/register."""
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # seconds until access token expires
    user: UserMeResponse


class MessageResponse(BaseModel):
    """Simple message response."""
    message: str
    success: bool = True
