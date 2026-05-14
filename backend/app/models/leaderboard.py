"""Leaderboard models — daily, weekly, and seasonal rankings.

Runtime leaderboard queries use Redis Sorted Sets for performance.
These SQL tables serve as persistent storage and source of truth.
"""

import uuid
from datetime import date, datetime

from sqlalchemy import Date, DateTime, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class LeaderboardDaily(Base):
    """Daily leaderboard — resets at 00:00 each night."""

    __tablename__ = "leaderboard_daily"
    __table_args__ = (
        UniqueConstraint("user_id", "date", name="uq_daily_user_date"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    date: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<LeaderboardDaily(user={self.user_id}, score={self.score}, date={self.date})>"


class LeaderboardWeekly(Base):
    """Weekly leaderboard — resets Monday 00:00."""

    __tablename__ = "leaderboard_weekly"
    __table_args__ = (
        UniqueConstraint("user_id", "week_start", name="uq_weekly_user_week"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    week_start: Mapped[date] = mapped_column(Date, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<LeaderboardWeekly(user={self.user_id}, score={self.score}, week={self.week_start})>"


class LeaderboardSeasonal(Base):
    """Seasonal leaderboard — 3-month seasons."""

    __tablename__ = "leaderboard_seasonal"
    __table_args__ = (
        UniqueConstraint("user_id", "season_id", name="uq_seasonal_user_season"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    score: Mapped[int] = mapped_column(Integer, default=0)
    season_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    def __repr__(self) -> str:
        return f"<LeaderboardSeasonal(user={self.user_id}, score={self.score}, season={self.season_id})>"
