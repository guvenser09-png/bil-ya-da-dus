"""Ranked sezon (aylık sıralama) modelleri.

ÖNEMLİ: Bu, Battle Pass'ten (User.season_points) AYRIDIR. Buradaki puanlar
season_id ("YYYY-MM") ile ilişkilidir → her ay yeni satırlar oluşur, eski sezon
satırları kalır (arşiv) ama yeni sezonda sıralama sıfırdan başlar.

PAY-TO-WIN YOK: Buradaki puan sadece OYUN PERFORMANSINDAN gelir (turnuva 3x
çarpanlı, normal maç 1x). Para/altın doğrudan puan eklemez.
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class SeasonScore(Base):
    """Bir kullanıcının belirli bir ranked sezondaki toplam puanı.

    (user_id, season_id) benzersiz → her kullanıcı her sezon için tek satır.
    """

    __tablename__ = "season_scores"
    __table_args__ = (
        UniqueConstraint("user_id", "season_id", name="uq_season_scores_user_season"),
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
    # "YYYY-MM" — sezonun BAŞLADIĞI ayın ilk-pazartesisinden türetilir.
    season_id: Mapped[str] = mapped_column(String(7), nullable=False, index=True)
    points: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now()
    )


class SeasonSettlement(Base):
    """Bir ranked sezonun ödül dağıtımının (settlement) yapıldığını işaretler.

    Idempotency: settle_season aynı season_id için iki kez ödül dağıtmasın diye
    önce bu tabloya satır yazar (varsa atlar).
    """

    __tablename__ = "season_settlements"

    season_id: Mapped[str] = mapped_column(String(7), primary_key=True)
    settled_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Kaç kullanıcıya ödül verildiği (gözlemlenebilirlik).
    rewarded_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
