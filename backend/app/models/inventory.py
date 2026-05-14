"""Transaction and Inventory models — in-game economy."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class TransactionType(str, enum.Enum):
    """Types of currency transactions."""
    PURCHASE = "purchase"    # Bought with real money
    REWARD = "reward"        # Earned from gameplay
    SPEND = "spend"          # Spent on items


class CurrencyType(str, enum.Enum):
    """In-game currency types."""
    COIN = "coin"    # Soft currency (earned)
    GEM = "gem"      # Hard currency (bought)
    REAL = "real"    # Real money


class ItemType(str, enum.Enum):
    """Cosmetic item categories."""
    AVATAR = "avatar"
    FRAME = "frame"
    EFFECT = "effect"
    EMOTE = "emote"
    BADGE = "badge"


class Transaction(Base):
    """Record of currency gains and spends."""

    __tablename__ = "transactions"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    type: Mapped[TransactionType] = mapped_column(
        Enum(TransactionType, name="transaction_type"), nullable=False
    )
    currency: Mapped[CurrencyType] = mapped_column(
        Enum(CurrencyType, name="currency_type"), nullable=False
    )
    amount: Mapped[int] = mapped_column(Integer, nullable=False)
    item_id: Mapped[str | None] = mapped_column(String(50), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Transaction(user={self.user_id}, type={self.type}, amount={self.amount})>"


class InventoryItem(Base):
    """Items owned by a player (cosmetics, badges, etc.)."""

    __tablename__ = "inventory"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    item_id: Mapped[str] = mapped_column(String(50), nullable=False)
    item_type: Mapped[ItemType] = mapped_column(
        Enum(ItemType, name="item_type"), nullable=False
    )
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<InventoryItem(user={self.user_id}, item={self.item_id}, type={self.item_type})>"
