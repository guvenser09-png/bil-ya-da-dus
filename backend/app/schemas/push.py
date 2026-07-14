"""Push bildirimi şemaları — cihaz token kaydı/silme."""

from typing import Literal

from pydantic import BaseModel, Field


class PushTokenRequest(BaseModel):
    """Cihaz token kaydı (upsert) / silme gövdesi."""

    token: str = Field(
        ..., min_length=10, max_length=255,
        description="FCM registration token (cihaz başına benzersiz).",
    )
    platform: Literal["ios", "android"] = Field(
        "ios", description="Cihaz platformu."
    )


class PushTokenResponse(BaseModel):
    """Kayıt sonucu. `push_enabled`: sunucuda Firebase kimlik bilgisi var mı?

    Kimlik bilgisi yoksa token yine SAKLANIR (kurulum tamamlanınca birikmiş
    token'lara gönderim yapılabilsin diye) ama gönderim yapılamaz.
    """

    success: bool = True
    push_enabled: bool = False
    message: str = "Bildirim token'ı kaydedildi."
