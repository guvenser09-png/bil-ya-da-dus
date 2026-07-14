"""Admin analitik ucu — hafif, SDK'sız metrikler (paylaşılan anahtar korumalı).

GET /api/admin/metrics?key=<ADMIN_METRICS_KEY>

Kimlik doğrulama JWT DEĞİL, tek bir paylaşılan anahtardır (settings.ADMIN_METRICS_KEY).
Anahtar boşsa (yani özellik yapılandırılmamışsa) veya yanlışsa 403 döner —
böylece anahtar set edilmeden uç yanlışlıkla açık kalmaz.

Örnek yanıt:
{
  "generated_at": "2026-07-14T09:00:00+00:00",
  "users": {"total": 1200, "registered": 800, "guest": 400},
  "new_users": {"last_1d": 40, "last_7d": 260, "last_30d": 1200},
  "daily": [                       # en yeni gün önce, son 7 gün
    {"date": "2026-07-14", "dau": 180, "matches": 420},
    ...
  ],
  "retention": {"d1_pct": 34.2, "d7_pct": 12.5},   # hesaplanamıyorsa null
  "redis_available": true
}
"""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.services import analytics_service

router = APIRouter()


def _verify_key(key: str) -> None:
    """Paylaşılan anahtarı doğrula; boş yapılandırma ya da uyumsuzluk → 403."""
    configured = settings.ADMIN_METRICS_KEY or ""
    # Anahtar hiç ayarlanmamışsa uç kapalıdır; yanlış anahtar da reddedilir.
    if not configured or key != configured:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Yetkisiz.",
        )


@router.get("/metrics")
async def get_metrics(
    key: str = Query("", description="Paylaşılan admin metrik anahtarı."),
    db: AsyncSession = Depends(get_db),
):
    """Analitik özetini döndür (DAU/retention/yeni kullanıcı/maç sayısı)."""
    _verify_key(key)
    return await analytics_service.compute_metrics(db)
