"""DeviceToken model — push bildirimi (FCM) cihaz token'ları.

Bir kullanıcının BİRDEN FAZLA cihazı olabilir (telefon + tablet) → user_id
tekil DEĞİL, yalnızca indekslidir. `token` ise küreseldir ve TEKİLDİR: aynı
FCM token'ı iki kullanıcıya bağlanamaz (cihaz el değiştirirse token yeni
kullanıcıya taşınır, bkz. PushService.register_token).

Gizlilik: token yalnızca OYUN bildirimi göndermek için tutulur; reklam/izleme
amacıyla kullanılmaz. Hesap silinince (delete_account) ve kullanıcı çıkış
yapınca temizlenir.
"""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class DeviceToken(Base):
    """Kullanıcının bir cihazına ait FCM push token'ı."""

    __tablename__ = "device_tokens"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # FCM registration token. Uzunluk sabit değildir (~163+ karakter) ve Google
    # zamanla uzatabilir → geniş tutuldu.
    token: Mapped[str] = mapped_column(
        String(255), unique=True, nullable=False, index=True
    )
    # "ios" | "android"
    platform: Mapped[str] = mapped_column(String(10), nullable=False, default="ios")

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    # Her token yenilemesinde/uygulama açılışında tazelenir → "ölü" token'ları
    # (aylardır görünmeyen cihazlar) ayıklamak için kullanılabilir.
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    def __repr__(self) -> str:
        return f"<DeviceToken(user_id={self.user_id}, platform={self.platform})>"
