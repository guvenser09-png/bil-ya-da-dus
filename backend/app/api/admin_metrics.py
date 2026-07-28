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


@router.get("/landing")
async def get_landing_stats(
    key: str = Query("", description="Paylaşılan admin metrik anahtarı."),
    days: int = Query(7, ge=1, le=30),
):
    """Reklam/bio açılış sayfası istatistikleri (kaynak bazlı atribüsyon).

    /indir sayfasına ?src=ig gibi etiketle gelen ziyaret ve mağaza tıklamaları
    Redis'te günlük sayılır. Bu uç onları okunur biçimde döndürür:
    "Instagram reklamı bugün kaç tıklama getirdi" sorusunun cevabı.
    """
    from datetime import datetime, timedelta, timezone

    from app.redis_client import get_redis

    _verify_key(key)
    out: list[dict] = []
    try:
        redis = await get_redis()
        today = datetime.now(timezone.utc).date()
        for i in range(days):
            d = (today - timedelta(days=i)).strftime("%Y-%m-%d")
            # Kaynaklar bilinmediğinden desenle tara (kayıt sayısı düşük).
            views: dict[str, int] = {}
            clicks: dict[str, int] = {}
            async for k in redis.scan_iter(match=f"landing:*:{d}:*", count=200):
                key_str = k.decode() if isinstance(k, bytes) else str(k)
                parts = key_str.split(":")
                if len(parts) < 4:
                    continue
                kind, src = parts[1], parts[3]
                val = int(await redis.get(key_str) or 0)
                (views if kind == "view" else clicks)[src] = (
                    (views if kind == "view" else clicks).get(src, 0) + val
                )
            if views or clicks:
                out.append({"date": d, "views": views, "clicks": clicks})
    except Exception as exc:  # Redis yoksa boş dön — panel çökmesin
        return {"error": str(exc), "days": []}
    return {"days": out}
