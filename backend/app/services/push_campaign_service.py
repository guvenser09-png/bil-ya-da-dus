"""Retention push kampanyaları — hedef kitle seçimi + mesaj metinleri.

Üç kampanya (hepsi `scripts/send_push_campaign.py` ile tetiklenir):

  streak   → Günlük ödül SERİSİ bugün bozulacak olanlar.        (20:00 TRT)
  daily    → Bugün "Günün Sorusu"nu oynamamış aktif oyuncular.   (12:00 TRT)
  comeback → 3+ gündür uygulamaya dönmemiş oyuncular.            (esnek)

ORTAK KURALLAR (hepsi burada uygulanır):
  • Yalnızca cihaz token'ı OLAN kullanıcılar hedeflenir (join device_tokens).
  • Silinmiş (deleted_at) / banlı (is_banned) / pasif hesaplar HARİÇ.
  • Sessiz saat + kişi başı günde 1 push sınırı gönderim anında push_service
    tarafından uygulanır (bkz. send_to_users).

Aktiflik verisi analytics_service'in Redis DAU setlerinden okunur
(`dau:YYYY-MM-DD`, UTC gün). Redis erişilemezse aktiflik gerektiren kampanyalar
DB'deki `last_login_at`e düşer (bozulmaz, sadece daha kaba olur).
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app import redis_client
from app.models.device_token import DeviceToken
from app.models.user import User
from app.services import analytics_service, daily_challenge_service

logger = logging.getLogger("app.push.campaign")

# Kampanya adı → (başlık, gövde, data payload). `data.type` mobil tarafta
# deep-link için kullanılır (bkz. mobile/lib/core/services/push_service.dart).
CAMPAIGNS: dict[str, dict] = {
    "streak": {
        "title": "Serin tehlikede! 🔥",
        "body": "Günlük ödülünü almazsan serin bu gece sıfırlanır. 30 saniyeni al.",
        "data": {"type": "streak", "route": "/home"},
    },
    "daily": {
        "title": "Günün Sorusu seni bekliyor 🧠",
        "body": "Bugünkü soruyu henüz çözmedin. Rakiplerin çoktan puanı kaptı!",
        # Doğrudan Günün Sorusu ekranına düşer (mobil rota: /daily).
        "data": {"type": "daily", "route": "/daily"},
    },
    "comeback": {
        "title": "Seni özledik! 👋",
        "body": "Yeni sorular, yeni rakipler. Bir maç at, sıralamanı geri al.",
        "data": {"type": "comeback", "route": "/home"},
    },
}

# comeback: bu kadar gündür dönmeyenler hedeflenir.
COMEBACK_MIN_IDLE_DAYS = 3
# comeback: çok eskiden kaybedilmiş (ölü token'lı) kitleyi rahatsız etmemek için
# üst sınır — son 30 gün içinde en az bir kez görülmüş olmalı.
COMEBACK_MAX_IDLE_DAYS = 30
# daily: "aktif oyuncu" tanımı — son bu kadar gün içinde uygulamayı açmış.
DAILY_ACTIVE_WINDOW_DAYS = 7


async def _active_user_ids(days: int, *, now: datetime | None = None) -> set[str] | None:
    """Son `days` günün DAU setlerinin birleşimi (UTC gün). Redis yoksa None."""
    now = now or datetime.now(timezone.utc)
    today = now.astimezone(timezone.utc).date()
    try:
        redis = await redis_client.get_redis()
        active: set[str] = set()
        for i in range(days):
            day = analytics_service._day_str(today - timedelta(days=i))
            members = await redis.smembers(analytics_service.dau_key(day))
            active |= {str(m) for m in members}
        return active
    except Exception as exc:
        logger.warning("DAU setleri okunamadı (Redis): %s", exc)
        return None


async def _users_with_tokens(db: AsyncSession) -> list[User]:
    """Cihaz token'ı olan, silinmemiş/banlanmamış tüm kullanıcılar."""
    rows = await db.execute(
        select(User)
        .join(DeviceToken, DeviceToken.user_id == User.id)
        .where(
            User.deleted_at.is_(None),
            User.is_banned.is_(False),
            User.is_active.is_(True),
        )
        .distinct()
    )
    return list(rows.scalars().all())


# ---------------------------------------------------------------------------
# Kampanya hedefleri
# ---------------------------------------------------------------------------

async def select_streak_targets(
    db: AsyncSession, *, now: datetime | None = None
) -> list[str]:
    """Günlük ödül serisi BUGÜN bozulacak olanlar.

    Günlük ödül UTC gün bazlıdır (bkz. daily_service): son alım DÜN ise seri
    canlıdır ama bugün alınmazsa UTC gece yarısında sıfırlanır. Yani hedef:
      • daily_streak >= 1  (kaybedecek bir serisi var)
      • son alım tarihi (UTC gün) == DÜN  (bugün henüz almamış → seri risk altında)
    Son alımı BUGÜN olanlar (zaten almış) ve daha eski olanlar (seri zaten
    bozulmuş) hariç tutulur.
    """
    now = now or datetime.now(timezone.utc)
    today_utc = now.astimezone(timezone.utc).date()
    yesterday_utc = today_utc - timedelta(days=1)

    targets: list[str] = []
    for user in await _users_with_tokens(db):
        if (user.daily_streak or 0) < 1:
            continue
        last = user.last_daily_claim_at
        if last is None:
            continue
        if last.tzinfo is None:
            last = last.replace(tzinfo=timezone.utc)
        if last.astimezone(timezone.utc).date() == yesterday_utc:
            targets.append(str(user.id))
    return targets


async def select_daily_targets(
    db: AsyncSession, *, now: datetime | None = None
) -> list[str]:
    """Bugünün "Günün Sorusu"nu OYNAMAMIŞ aktif oyuncular.

    "Aktif" = son DAILY_ACTIVE_WINDOW_DAYS gün içinde uygulamayı açmış (DAU).
    Redis yoksa DB'deki last_login_at'e düşülür. Oynamış olanlar
    daily_challenge_service.has_played_today ile elenir (TRT gün bazlı).
    """
    now = now or datetime.now(timezone.utc)
    active = await _active_user_ids(DAILY_ACTIVE_WINDOW_DAYS, now=now)
    fallback_threshold = now - timedelta(days=DAILY_ACTIVE_WINDOW_DAYS)

    targets: list[str] = []
    for user in await _users_with_tokens(db):
        uid = str(user.id)

        if active is not None:
            if uid not in active:
                continue
        else:
            # Redis yok → DB'deki son giriş damgasına düş.
            last_login = user.last_login_at
            if last_login is None:
                continue
            if last_login.tzinfo is None:
                last_login = last_login.replace(tzinfo=timezone.utc)
            if last_login < fallback_threshold:
                continue

        if await daily_challenge_service.has_played_today(uid):
            continue
        targets.append(uid)
    return targets


async def select_comeback_targets(
    db: AsyncSession, *, now: datetime | None = None
) -> list[str]:
    """COMEBACK_MIN_IDLE_DAYS+ gündür dönmemiş (ama son 30 günde görülmüş) oyuncular.

    DAU setlerinde son 3 gündür GÖRÜNMEYEN, ama son 30 gün içinde en az bir kez
    giriş yapmış kullanıcılar. Redis yoksa yalnızca last_login_at penceresi
    kullanılır.
    """
    now = now or datetime.now(timezone.utc)
    recent = await _active_user_ids(COMEBACK_MIN_IDLE_DAYS, now=now)

    idle_after = now - timedelta(days=COMEBACK_MIN_IDLE_DAYS)   # bundan sonra görüldüyse hariç
    idle_before = now - timedelta(days=COMEBACK_MAX_IDLE_DAYS)  # bundan önce ise çok eski

    targets: list[str] = []
    for user in await _users_with_tokens(db):
        uid = str(user.id)

        # Son 3 günde DAU'da görünüyorsa hedef değil.
        if recent is not None and uid in recent:
            continue

        # Son giriş damgası: hiç yoksa kayıt tarihine düş (yeni açıp bir daha
        # dönmemiş kullanıcı da geri kazanılmaya değer).
        last_seen = user.last_login_at or user.created_at
        if last_seen is None:
            continue
        if last_seen.tzinfo is None:
            last_seen = last_seen.replace(tzinfo=timezone.utc)

        if last_seen > idle_after:
            continue  # son 3 gün içinde görülmüş
        if last_seen < idle_before:
            continue  # 30 günden eski → rahatsız etme
        targets.append(uid)
    return targets


_SELECTORS = {
    "streak": select_streak_targets,
    "daily": select_daily_targets,
    "comeback": select_comeback_targets,
}


async def select_targets(
    db: AsyncSession, campaign: str, *, now: datetime | None = None
) -> list[str]:
    """Kampanya adına göre hedef kullanıcı id listesi. Bilinmeyen ad → ValueError."""
    selector = _SELECTORS.get(campaign)
    if selector is None:
        raise ValueError(
            f"Bilinmeyen kampanya: {campaign!r}. Geçerli: {', '.join(_SELECTORS)}"
        )
    return await selector(db, now=now)
