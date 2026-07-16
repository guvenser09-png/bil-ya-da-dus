"""Ödüllü reklam ödülü servisi (pay-to-win YOK).

İstemci bir ödüllü reklam izlediğini bildirdiğinde güvenli şekilde ödül verir.
Ödül YALNIZCA coin/kozmetiktir — oyun içi avantaj (doğru cevap, ekstra süre,
joker, kalıcı puan) ASLA verilmez.

Anti-fraud:
  - Günlük toplam limit: kullanıcı başına günde max ADS_DAILY_LIMIT ödüllü reklam.
  - Placement başına günlük cap: her yerleşim için ayrı limit.
  - Idempotency (nonce): aynı nonce ile gelen istek tekrar ödüllendirilmez
    (Redis SET NX). Redis yoksa best-effort; günlük sayaç DB'de tutulur.

Sayaç UTC gün bazlı User.ad_reward_date / ad_reward_count_today alanlarında.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.redis_client import get_redis
from app.services.user_service import UserService

logger = logging.getLogger("app.ads_service")

# Günlük toplam ödüllü reklam limiti (COIN veren yerleşimler toplamı).
# NOT: Kalkan reklamı (placement="shield") altın VERMEZ → bu toplama DAHİL
# DEĞİLDİR; kendi ayrı günlük cap'i (SHIELD_AD_DAILY_CAP) vardır.
ADS_DAILY_LIMIT = 5

# Yerleşim (placement) tanımları: ödül + placement başına günlük cap.
# reward: {"coins": int}. SADECE coin (pay-to-win YOK).
# "gold": ekonomi kıtlaştırmasının telafisi — oyuncu reklam izleyerek +100 altın
# alır (kalkan/karakter için ana kazanç yolu). Günlük cap ile kötüye kullanım
# engellenir (mevcut cap deseni korunur).
#
# ⚠️ TUTARLILIK SÖZLEŞMESİ: buradaki "gold" coin miktarı, mağazada GÖSTERİLEN
# miktarla (store_screen.dart "+100 altın") BİREBİR aynı olmak ZORUNDA. Bir
# tarafı değiştirirsen diğerini de değiştir; aksi halde kullanıcı gösterilenden
# farklı altın alır (eski 200↔100 tutarsızlığı buradan doğmuştu).
PLACEMENTS: dict[str, dict] = {
    "daily_coins": {"reward": {"coins": 50}, "daily_cap": 3},
    "double_match": {"reward": {"coins": 30}, "daily_cap": 3},
    "shop_bonus": {"reward": {"coins": 40}, "daily_cap": 2},
    "gold": {"reward": {"coins": 100}, "daily_cap": 3},
}

# --- Kalkan reklamı (ödüllü reklamla "bedava kalkan kredisi") ---
# Altın VERMEZ; yalnızca prepare-shield akışında shield_ready bayrağını haklı
# kılacak ANTI-FRAUD doğrulaması sağlar. Coin toplam limitinden (ADS_DAILY_LIMIT)
# bağımsız kendi günlük cap'i vardır (para vektörü olmadığı için ayrı tutulur).
SHIELD_AD_PLACEMENT = "shield"
SHIELD_AD_DAILY_CAP = 10

_NONCE_TTL = 24 * 3600


def _utc_day(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


class AdsService:
    """Ödüllü reklam ödül iş mantığı."""

    @staticmethod
    async def grant_reward(
        db: AsyncSession,
        user_id: str,
        placement: str,
        nonce: str | None = None,
        *,
        now: datetime | None = None,
    ) -> dict:
        """Ödüllü reklam ödülünü ver (anti-fraud + günlük limit + idempotency).

        Raises:
            ValueError: Geçersiz placement, limit aşıldı veya kullanıcı yok.
        """
        now = now or datetime.now(timezone.utc)

        pl = PLACEMENTS.get(placement)
        if not pl:
            raise ValueError(f"Geçersiz reklam yerleşimi: {placement}")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        # --- Günlük toplam limit (UTC gün bazlı) ---
        today = _utc_day(now)
        if user.ad_reward_date != today:
            user.ad_reward_date = today
            user.ad_reward_count_today = 0

        if (user.ad_reward_count_today or 0) >= ADS_DAILY_LIMIT:
            raise ValueError("Günlük ödüllü reklam limitine ulaştınız.")

        # --- Placement başına günlük cap (Redis sayaç; yoksa best-effort) ---
        placement_cap = int(pl.get("daily_cap", ADS_DAILY_LIMIT))
        placement_count = 0
        redis_ok = False
        pkey = f"ad:placement:{user_id}:{today}:{placement}"
        try:
            redis = await get_redis()
            placement_count = int(await redis.get(pkey) or 0)
            redis_ok = True
            if placement_count >= placement_cap:
                raise ValueError(
                    "Bu reklam türü için günlük limite ulaştınız."
                )
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Ad placement sayaç kontrolü atlandı: %s", exc)

        # --- Idempotency (nonce) ---
        # BİLEREK limit kontrollerinden SONRA, ödülün hemen ÖNCESİNDE yakılır:
        # limit/doğrulama hatası nonce'u boşa harcamaz — aynı izlemenin meşru
        # tekrarı (geçici hata sonrası) "zaten alındı"ya düşüp ödülü yutmaz.
        # Aynı nonce'la eşzamanlı iki istek yine SET NX ile serileşir.
        if nonce:
            try:
                redis = await get_redis()
                first = await redis.set(
                    f"ad:nonce:{user_id}:{nonce}", "1", nx=True, ex=_NONCE_TTL
                )
                if first is None:
                    raise ValueError("Bu reklam ödülü zaten alındı.")
            except ValueError:
                raise
            except Exception as exc:
                logger.warning("Ad nonce kontrolü atlandı: %s", exc)

        # --- Ödülü uygula (SADECE coin) ---
        reward = pl["reward"]
        coins = int(reward.get("coins", 0))
        user.coins = (user.coins or 0) + coins
        user.ad_reward_count_today = (user.ad_reward_count_today or 0) + 1

        await db.flush()
        await db.refresh(user)

        # Placement sayacını artır (best-effort).
        if redis_ok:
            try:
                redis = await get_redis()
                await redis.incr(pkey)
                await redis.expire(pkey, _NONCE_TTL)
            except Exception as exc:
                logger.warning("Ad placement sayaç artırılamadı: %s", exc)

        return {
            "granted": True,
            "placement": placement,
            "reward": {"coins": coins},
            "coins": user.coins,
            "daily_remaining": max(0, ADS_DAILY_LIMIT - (user.ad_reward_count_today or 0)),
        }

    @staticmethod
    async def verify_shield_ad(
        user_id: str,
        nonce: str | None = None,
        *,
        now: datetime | None = None,
    ) -> dict:
        """Kalkan reklamının izlendiğini doğrula (altın VERMEZ; yalnızca anti-fraud).

        prepare_shield(source="ad") buradan geçer; başarılıysa çağıran taraf
        shield_ready bayrağını set eder. Coin akışından bağımsızdır: ne altın
        ekler ne ad_reward_count_today sayacına dokunur. Sadece:
          - nonce idempotency (Redis SET NX) — aynı reklam iki kez sayılmasın,
          - kalkan reklamı için AYRI günlük cap (SHIELD_AD_DAILY_CAP).

        Redis erişilemezse fail-open (reklamı izleyen oyuncu cezalandırılmaz);
        bu, mevcut ads best-effort desenidir.

        Raises:
            ValueError: Aynı nonce tekrar geldi veya günlük kalkan reklamı cap'i aşıldı.
        """
        now = now or datetime.now(timezone.utc)
        today = _utc_day(now)

        # Deferred import: conftest testlerinde `app.redis_client.get_redis`
        # patch'lenir; yerel import patch'li mock'u yakalar (modül-üstü import
        # bunu kaçırırdı → gerçek Redis'e gidip test'i yavaşlatırdı).
        from app.redis_client import get_redis

        # --- Idempotency (nonce) ---
        if nonce:
            try:
                redis = await get_redis()
                first = await redis.set(
                    f"ad:nonce:shield:{user_id}:{nonce}", "1", nx=True, ex=_NONCE_TTL
                )
                if first is None:
                    raise ValueError("Bu kalkan reklamı zaten kullanıldı.")
            except ValueError:
                raise
            except Exception as exc:
                logger.warning("Kalkan reklamı nonce kontrolü atlandı: %s", exc)

        # --- Kalkan reklamı için ayrı günlük cap (Redis sayaç) ---
        pkey = f"ad:placement:{user_id}:{today}:{SHIELD_AD_PLACEMENT}"
        redis_ok = False
        try:
            redis = await get_redis()
            count = int(await redis.get(pkey) or 0)
            redis_ok = True
            if count >= SHIELD_AD_DAILY_CAP:
                raise ValueError("Günlük kalkan reklamı limitine ulaştınız.")
        except ValueError:
            raise
        except Exception as exc:
            logger.warning("Kalkan reklamı cap kontrolü atlandı: %s", exc)

        if redis_ok:
            try:
                redis = await get_redis()
                await redis.incr(pkey)
                await redis.expire(pkey, _NONCE_TTL)
            except Exception as exc:
                logger.warning("Kalkan reklamı sayacı artırılamadı: %s", exc)

        return {"verified": True, "placement": SHIELD_AD_PLACEMENT}
