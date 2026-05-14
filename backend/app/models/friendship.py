"""Friendship model — social connections between players.

Friendship levels (from CLAUDE.md Section 5.3):
- 5 games together  → Tanıdık
- 20 games together → Dost
- 50 games together → Sıkı Dost
- 100 games together → Yoldaş
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class FriendshipLevel(str, enum.Enum):
    """Friendship progression tiers based on games played together."""
    TANIDIK = "tanidik"        # 5+ games
    DOST = "dost"              # 20+ games
    SIKI_DOST = "siki_dost"    # 50+ games
    YOLDAS = "yoldas"          # 100+ games


class Friendship(Base):
    """Friendship between two players."""

    __tablename__ = "friendships"
    __table_args__ = (
        UniqueConstraint("user1_id", "user2_id", name="uq_friendship_pair"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user1_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    user2_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    level: Mapped[FriendshipLevel] = mapped_column(
        Enum(FriendshipLevel, name="friendship_level"),
        default=FriendshipLevel.TANIDIK,
    )
    games_together: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def update_level(self) -> None:
        """Auto-update friendship level based on games played together."""
        if self.games_together >= 100:
            self.level = FriendshipLevel.YOLDAS
        elif self.games_together >= 50:
            self.level = FriendshipLevel.SIKI_DOST
        elif self.games_together >= 20:
            self.level = FriendshipLevel.DOST
        else:
            self.level = FriendshipLevel.TANIDIK

    def __repr__(self) -> str:
        return f"<Friendship(user1={self.user1_id}, user2={self.user2_id}, level={self.level})>"
