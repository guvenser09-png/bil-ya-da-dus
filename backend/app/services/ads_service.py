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

# Günlük toplam ödüllü reklam limiti (tüm yerleşimler toplamı).
ADS_DAILY_LIMIT = 5

# Yerleşim (placement) tanımları: ödül + placement başına günlük cap.
# reward: {"coins": int}. SADECE coin (pay-to-win YOK).
PLACEMENTS: dict[str, dict] = {
    "daily_coins": {"reward": {"coins": 50}, "daily_cap": 3},
    "double_match": {"reward": {"coins": 30}, "daily_cap": 3},
    "shop_bonus": {"reward": {"coins": 40}, "daily_cap": 2},
}

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

        # --- Idempotency (nonce) ---
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
