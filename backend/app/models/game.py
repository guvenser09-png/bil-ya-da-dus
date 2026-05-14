"""Game and GameParticipant models — match tracking."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class GameStatus(str, enum.Enum):
    """Game lifecycle states."""
    WAITING = "waiting"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class Game(Base):
    """A single match/game session."""

    __tablename__ = "games"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True)
    )
    winner_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    player_count: Mapped[int] = mapped_column(Integer, nullable=False)
    bot_count: Mapped[int] = mapped_column(Integer, default=0)
    status: Mapped[GameStatus] = mapped_column(
        Enum(GameStatus, name="game_status"),
        default=GameStatus.WAITING,
    )
    lobby_code: Mapped[str | None] = mapped_column(
        String(10), unique=True, nullable=True
    )
    current_round: Mapped[int] = mapped_column(Integer, default=0)

    # Relationships
    winner = relationship(
        "User", back_populates="won_games", foreign_keys=[winner_id], lazy="selectin"
    )
    participants = relationship(
        "GameParticipant", back_populates="game", lazy="selectin",
        cascade="all, delete-orphan",
    )

    def __repr__(self) -> str:
        return f"<Game(id={self.id}, status={self.status}, players={self.player_count})>"


class GameParticipant(Base):
    """A player (real or bot) in a game."""

    __tablename__ = "game_participants"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id"), nullable=True
    )
    bot_name: Mapped[str | None] = mapped_column(String(30))
    is_bot: Mapped[bool] = mapped_column(Boolean, default=False)
    final_round: Mapped[int] = mapped_column(Integer, default=0)
    score: Mapped[int] = mapped_column(Integer, default=0)
    joined_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    eliminated_at_round: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    game = relationship("Game", back_populates="participants")
    user = relationship("User", back_populates="game_participations")

    def __repr__(self) -> str:
        name = self.bot_name if self.is_bot else f"user:{self.user_id}"
        return f"<GameParticipant(game={self.game_id}, {name}, score={self.score})>"
