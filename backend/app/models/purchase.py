"""Satın alma (IAP) modelleri — gerçek para kazanma altyapısı.

Bu modeller Ajan B tarafından eklendi. Mevcut `inventory.py` içindeki
`InventoryItem` (kozmetik eşyalar) ile karışmaması için kalıcı sahiplikler
ayrı bir `Entitlement` tablosunda tutulur (karakter paketleri, premium vb.).

Para birimi (coins = altın) ve premium bayrakları User üzerinde tutulur;
burada sadece "neye sahip olunduğu" (entitlement) ve "ne satın alındığı"
(purchase) kaydedilir.
"""

import enum
import uuid
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class PurchasePlatform(str, enum.Enum):
    """Satın almanın yapıldığı mağaza platformu."""
    IOS = "ios"
    ANDROID = "android"


class PurchaseStatus(str, enum.Enum):
    """Bir satın alma kaydının doğrulama durumu."""
    PENDING = "pending"      # Doğrulama bekliyor
    VERIFIED = "verified"    # Makbuz doğrulandı, ürün verildi
    FAILED = "failed"        # Doğrulama başarısız


class EntitlementType(str, enum.Enum):
    """Kullanıcının sahip olabileceği kalıcı haklar."""
    CHARACTER_PACK = "character_pack"  # örn pack_animals
    PREMIUM = "premium"                # premium abonelik hakkı
    COINS = "coins"                    # consumable; iz amaçlı (asıl bakiye User'da)


class Purchase(Base):
    """Tek bir IAP satın alma kaydı (idempotent — transaction_id UNIQUE)."""

    __tablename__ = "purchases"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    platform: Mapped[PurchasePlatform] = mapped_column(
        Enum(PurchasePlatform, name="purchase_platform"), nullable=False
    )
    product_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    # Mağaza işlem kimliği — tekrar işlemeyi önlemek için UNIQUE.
    transaction_id: Mapped[str] = mapped_column(
        String(255), nullable=False, unique=True, index=True
    )
    status: Mapped[PurchaseStatus] = mapped_column(
        Enum(PurchaseStatus, name="purchase_status"),
        nullable=False, default=PurchaseStatus.PENDING,
    )
    # Opsiyonel para bilgisi (mağazadan gelebilir; raporlama için).
    amount: Mapped[int | None] = mapped_column(Integer, nullable=True)  # kuruş/cent
    currency: Mapped[str | None] = mapped_column(String(10), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Purchase(user={self.user_id}, product={self.product_id}, "
            f"status={self.status})>"
        )


class Entitlement(Base):
    """Kullanıcının kalıcı sahip olduğu haklar (karakter paketi, premium...).

    Altın (coins) consumable olduğu için User üzerinde tutulur; bu tablo
    "restore purchases" için non-consumable sahiplikleri saklar.
    Aynı kullanıcı + aynı item için tek kayıt olur (uygulama katmanında garanti).
    """

    __tablename__ = "entitlements"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    item_type: Mapped[EntitlementType] = mapped_column(
        Enum(EntitlementType, name="entitlement_type"), nullable=False
    )
    # örn 'pack_animals', 'premium_monthly'
    item_id: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    granted_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return (
            f"<Entitlement(user={self.user_id}, item={self.item_id}, "
            f"type={self.item_type})>"
        )
