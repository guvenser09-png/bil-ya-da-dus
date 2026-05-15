"""User model — player accounts and profiles."""

import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.database import Base


class User(Base):
    """Player account with profile, stats, and currency."""

    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    username: Mapped[str] = mapped_column(
        String(30), unique=True, nullable=False, index=True
    )
    email: Mapped[str | None] = mapped_column(
        String(255), unique=True, nullable=True, index=True
    )
    phone: Mapped[str | None] = mapped_column(
        String(20), unique=True, nullable=True
    )
    password_hash: Mapped[str | None] = mapped_column(String(255))

    # Auth provider (for future OAuth)
    auth_provider: Mapped[str | None] = mapped_column(
        String(20)  # "email", "google", "apple", None
    )
    auth_provider_id: Mapped[str | None] = mapped_column(String(255))

    # Profile
    display_name: Mapped[str | None] = mapped_column(String(50))
    avatar_id: Mapped[str] = mapped_column(
        String(100), default="default_01"
    )
    bio: Mapped[str | None] = mapped_column(String(140))
    interest_tags: Mapped[list | None] = mapped_column(
        JSON, nullable=True  # max 5 tags, e.g. ["sinema", "spor", "müzik"]
    )

    # Progression
    level: Mapped[int] = mapped_column(Integer, default=1)
    xp: Mapped[int] = mapped_column(Integer, default=0)
    season_level: Mapped[int] = mapped_column(Integer, default=1)

    # Currency
    coins: Mapped[int] = mapped_column(Integer, default=0)
    gems: Mapped[int] = mapped_column(Integer, default=0)

    # Stats
    games_played: Mapped[int] = mapped_column(Integer, default=0)
    games_won: Mapped[int] = mapped_column(Integer, default=0)
    win_rate: Mapped[float] = mapped_column(Float, default=0.0)
    total_score: Mapped[int] = mapped_column(Integer, default=0)
    best_streak: Mapped[int] = mapped_column(Integer, default=0)
    favorite_category: Mapped[str | None] = mapped_column(String(50))
    total_correct_answers: Mapped[int] = mapped_column(Integer, default=0)
    total_questions_answered: Mapped[int] = mapped_column(Integer, default=0)

    # Status
    is_banned: Mapped[bool] = mapped_column(Boolean, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    is_verified: Mapped[bool] = mapped_column(Boolean, default=False)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )
    last_login_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )

    # Relationships
    game_participations = relationship(
        "GameParticipant", back_populates="user", lazy="selectin"
    )
    won_games = relationship(
        "Game", back_populates="winner", foreign_keys="Game.winner_id", lazy="selectin"
    )

    @property
    def accuracy_rate(self) -> float:
        """Calculate answer accuracy percentage."""
        if self.total_questions_answered == 0:
            return 0.0
        return round(self.total_correct_answers / self.total_questions_answered * 100, 1)

    def __repr__(self) -> str:
        return f"<User(id={self.id}, username={self.username})>"
