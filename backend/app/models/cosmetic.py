"""Kozmetik sahiplik modeli — COIN ile alınan kozmetiklerin sahipliği.

Kozmetikler (çerçeve / isim rengi / efekt) yumuşak para (coins) ile alınır;
IAP DEĞİLDİR. Bu yüzden `purchase.py`'deki Entitlement tablosundan AYRI,
sade bir sahiplik tablosu kullanılır. Katalog (id/fiyat/slot) kod tarafında
`app/services/cosmetics_service.py` içinde sabit tutulur; burada sadece
"hangi kullanıcı hangi kozmetiğe sahip" kaydı saklanır.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class UserCosmetic(Base):
    """Bir kullanıcının sahip olduğu tek bir kozmetik kaydı.

    Aynı kullanıcı + aynı kozmetik için tek kayıt olur
    (UNIQUE(user_id, cosmetic_id)).
    """

    __tablename__ = "user_cosmetics"
    __table_args__ = (
        UniqueConstraint("user_id", "cosmetic_id", name="uq_user_cosmetic"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # Katalog kimliği, örn 'frame_gold', 'name_mint', 'fx_confetti'
    cosmetic_id: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    acquired_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<UserCosmetic(user={self.user_id}, cosmetic={self.cosmetic_id})>"
        )
