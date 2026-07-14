"""Hafif, SDK'sız analitik — Redis tabanlı DAU + günlük maç sayısı, DB kohortu.

MIGRATION YOK: tüm işaretleme/sayım Redis set + counter'larında ve mevcut
`users` tablosunun `created_at` / `is_guest` alanlarında yapılır. Şema riski
sıfır. Redis hataları uygulama akışını ASLA bozmaz — işaretleme fonksiyonları
tüm istisnaları yutar (best-effort).

Anahtarlar:
  dau:YYYY-MM-DD      -> o gün aktif olan (auth'lu) kullanıcı id'lerinin SET'i
  matches:YYYY-MM-DD  -> o gün biten maç sayacı (INCR)

Her iki anahtar da ~60 gün TTL ile yaşar (retention penceresi + pay payı).
"""

from __future__ import annotations

import logging
from datetime import date, datetime, time, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_client
from app.models.user import User

logger = logging.getLogger("app.analytics")

# DAU/maç anahtarlarının yaşam süresi (saniye). 60 gün: son 30 günün DAU'su +
# D7 retention için kohort penceresi rahatça sığar.
_ANALYTICS_TTL_SECONDS = 60 * 24 * 3600


def _utc_date(now: datetime | None = None) -> date:
    """Verilen (ya da şu anki) zamanın UTC gün tarihini döndür."""
    now = now or datetime.now(timezone.utc)
    return now.astimezone(timezone.utc).date()


def _day_str(d: date) -> str:
    return d.strftime("%Y-%m-%d")


def dau_key(day: str) -> str:
    return f"dau:{day}"


def matches_key(day: str) -> str:
    return f"matches:{day}"


# --- İşaretleme (best-effort; Redis hatasını yutar) ---

async def mark_daily_active(user_id: str | None, *, now: datetime | None = None) -> None:
    """Kimliği doğrulanmış kullanıcıyı bugünün DAU setine ekle.

    Sık çağrılan auth dependency'den çağrılır → maliyeti düşük olmalı ve
    Redis erişilemezse istek akışını ASLA bozmamalı (tüm hatalar yutulur).
    """
    if not user_id:
        return
    try:
        key = dau_key(_day_str(_utc_date(now)))
        redis = await redis_client.get_redis()
        await redis.sadd(key, str(user_id))
        # TTL'i her işaretlemede tazele (o günün seti ~60 gün yaşasın).
        await redis.expire(key, _ANALYTICS_TTL_SECONDS)
    except Exception as exc:  # analitik ASLA akışı bozmaz
        logger.debug("DAU işaretleme atlandı (user %s): %s", user_id, exc)


async def increment_match_count(*, now: datetime | None = None) -> None:
    """Biten bir maçı bugünün maç sayacına ekle (INCR). Redis hatasını yut.

    Maç-sonu idempotent bloğundan (maç başına TEK kez) çağrılır; mevcut ödül/XP
    kancalarıyla çakışmaz, yalnızca sayacı artırır.
    """
    try:
        key = matches_key(_day_str(_utc_date(now)))
        redis = await redis_client.get_redis()
        await redis.incr(key)
        await redis.expire(key, _ANALYTICS_TTL_SECONDS)
    except Exception as exc:  # analitik ASLA akışı bozmaz
        logger.debug("Maç sayacı artırılamadı: %s", exc)


# --- Okuma / raporlama ---

async def _retention_pct(
    db: AsyncSession,
    cohort_day: date,
    day_n: int,
) -> float | None:
    """Kohort retention yüzdesi.

    `cohort_day` gününde kaydolan kullanıcıların, `cohort_day + day_n` gününün
    DAU setinde bulunma oranı (%). Kohort boşsa ya da Redis okunamıyorsa None.
    """
    try:
        start = datetime.combine(cohort_day, time.min, tzinfo=timezone.utc)
        end = start + timedelta(days=1)
        rows = await db.execute(
            select(User.id).where(User.created_at >= start, User.created_at < end)
        )
        cohort = {str(r[0]) for r in rows.all()}
        if not cohort:
            return None
        redis = await redis_client.get_redis()
        active_raw = await redis.smembers(dau_key(_day_str(cohort_day + timedelta(days=day_n))))
        active = {str(a) for a in active_raw}
        retained = len(cohort & active)
        return round(100.0 * retained / len(cohort), 1)
    except Exception as exc:
        logger.debug("Retention hesaplanamadı (cohort %s, D%s): %s", cohort_day, day_n, exc)
        return None


async def compute_metrics(
    db: AsyncSession,
    *,
    now: datetime | None = None,
    days: int = 7,
) -> dict:
    """Analitik özetini derle (DB + Redis). Redis yoksa DB kısmı yine döner.

    Returns: JSON'a hazır sözlük (bkz. admin_metrics uç dokümantasyonu).
    """
    now = now or datetime.now(timezone.utc)
    today = _utc_date(now)

    # --- DB: kullanıcı sayıları (soft-delete edilenler hariç) ---
    active_filter = User.deleted_at.is_(None)
    total = await db.scalar(
        select(func.count()).select_from(User).where(active_filter)
    ) or 0
    guests = await db.scalar(
        select(func.count()).select_from(User).where(active_filter, User.is_guest.is_(True))
    ) or 0
    registered = total - guests

    # --- DB: yeni kayıtlar (son 1/7/30 gün, created_at'ten) ---
    async def _new_since(n: int) -> int:
        threshold = now - timedelta(days=n)
        return await db.scalar(
            select(func.count()).select_from(User).where(User.created_at >= threshold)
        ) or 0

    new_1d = await _new_since(1)
    new_7d = await _new_since(7)
    new_30d = await _new_since(30)

    # --- Redis: son N günün DAU + maç sayısı (en yeni gün önce) ---
    daily: list[dict] = []
    redis_available = True
    try:
        redis = await redis_client.get_redis()
        for i in range(days):
            d = today - timedelta(days=i)
            dk = _day_str(d)
            dau = await redis.scard(dau_key(dk))
            matches = await redis.get(matches_key(dk))
            daily.append({
                "date": dk,
                "dau": int(dau or 0),
                "matches": int(matches or 0),
            })
    except Exception as exc:
        redis_available = False
        daily = []
        logger.warning("Redis metrikleri okunamadı: %s", exc)

    # --- Retention (hesaplanabiliyorsa) ---
    # D1: dün kaydolan kohortun bugün aktif olma yüzdesi (bugün gün henüz
    #     dolmamış olabilir → alt sınır tahmin). D7: 7 gün önceki kohort.
    d1 = await _retention_pct(db, today - timedelta(days=1), 1) if redis_available else None
    d7 = await _retention_pct(db, today - timedelta(days=7), 7) if redis_available else None

    return {
        "generated_at": now.astimezone(timezone.utc).isoformat(),
        "users": {
            "total": int(total),
            "registered": int(registered),
            "guest": int(guests),
        },
        "new_users": {
            "last_1d": int(new_1d),
            "last_7d": int(new_7d),
            "last_30d": int(new_30d),
        },
        "daily": daily,
        "retention": {
            "d1_pct": d1,
            "d7_pct": d7,
        },
        "redis_available": redis_available,
    }
