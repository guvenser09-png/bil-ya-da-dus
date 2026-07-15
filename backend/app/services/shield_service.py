"""Kalkan hazırlama servisi (yeni ekonomi modeli).

Kalkan artık BEDAVA DEĞİLDİR. Kural:
  - Yeni oyuncu (games_played < 5): maça otomatik 1 bedava kalkanla başlar
    (kurulum game_service.apply_shield_setup'ta yapılır).
  - Diğer oyuncular: kalkan OTOMATİK GELMEZ. Oyuncu maç ÖNCESİ "kalkan hazırlar":
      • 100 altınla satın alır (source="gold"), VEYA
      • ödüllü reklam izleyerek bedava kredi kazanır (source="ad").
    Hazırlanınca Redis'te `shield_ready:{user_id}` bayrağı (TTL ~15 dk) set edilir.
    Maç başında game_service bu bayrağı görür → o maç için shields=1 verir ve
    bayrağı SİLER (tek kullanımlık).

Bu modül SADECE bayrak yönetimi + prepare akışını içerir. Bayrağı OKUYUP TÜKETEN
taraf game_service.GameEngine.apply_shield_setup'tır.
"""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService

logger = logging.getLogger("app.shield_service")

# Kalkan satın alma bedeli (altın).
SHIELD_GOLD_COST = 100

# shield_ready bayrağının yaşam süresi: oyuncu kalkanı hazırladıktan sonra makul
# bir süre içinde maça girmeli. ~15 dk.
SHIELD_READY_TTL = 15 * 60


def _ready_key(user_id: str) -> str:
    return f"shield_ready:{user_id}"


async def set_shield_ready(user_id: str) -> bool:
    """`shield_ready:{user_id}` bayrağını TTL ile set et.

    Redis erişilemezse False döner (çağıran taraf yine de {ok:true} dönebilir;
    ama pratikte prod'da Redis vardır). Best-effort.
    """
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        await redis.set(_ready_key(user_id), "1", ex=SHIELD_READY_TTL)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("shield_ready set edilemedi (user %s): %s", user_id, exc)
        return False


async def has_shield_ready(user_id: str) -> bool:
    """Kullanıcının aktif bir kalkan kredisi (bayrak) var mı? (SİLMEZ.)"""
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        return bool(await redis.get(_ready_key(user_id)))
    except Exception as exc:  # pragma: no cover
        logger.warning("shield_ready okunamadı (user %s): %s", user_id, exc)
        return False


async def consume_shield_ready(user_id: str) -> bool:
    """Bayrak varsa TÜKET (sil) ve True dön; yoksa False.

    Maç kurulumunda game_service çağırır — kalkan tek kullanımlıktır. Redis
    hatasında False (kalkan verilmez; oyuncu kredisini kaybetmez çünkü bayrak
    silinmemiştir → sonraki maça taşınır). Best-effort.
    """
    try:
        from app.redis_client import get_redis

        redis = await get_redis()
        key = _ready_key(user_id)
        exists = await redis.get(key)
        if not exists:
            return False
        await redis.delete(key)
        return True
    except Exception as exc:  # pragma: no cover
        logger.warning("shield_ready tüketilemedi (user %s): %s", user_id, exc)
        return False


async def prepare_shield(
    db: AsyncSession,
    user_id: str,
    source: str,
    nonce: str | None = None,
) -> dict:
    """Maç öncesi kalkan hazırla (altın ile satın al veya reklam kredisi).

    source="gold":
        Bakiye >= SHIELD_GOLD_COST ise 100 altın DÜŞ + bayrak set et →
        {ok:true, source:"gold", coins:yeni_bakiye}. Bakiye yetmezse ALTIN
        DÜŞMEZ → {ok:false, reason:"insufficient", coins:mevcut}.
    source="ad":
        Ödüllü reklam TAMAMLANDIKTAN sonra çağrılır. Reklam doğrulaması
        ads_service.verify_shield_ad üzerinden yapılır (altın DÜŞMEZ); doğrulama
        geçerse bayrak set edilir → {ok:true, source:"ad"}.

    Raises:
        ValueError: Geçersiz source, kullanıcı yok veya reklam doğrulaması
            (nonce tekrarı / günlük cap) başarısız.
    """
    if source == "gold":
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")
        balance = user.coins or 0
        if balance < SHIELD_GOLD_COST:
            # Altına dokunma; mobil "yetersiz altın" gösterir.
            return {"ok": False, "reason": "insufficient", "coins": balance}
        user.coins = balance - SHIELD_GOLD_COST
        await db.flush()
        await db.refresh(user)
        await set_shield_ready(user_id)
        return {"ok": True, "source": "gold", "coins": user.coins or 0}

    if source == "ad":
        # Reklam doğrulaması ads_service üzerinden (placement "shield").
        from app.services.ads_service import AdsService

        await AdsService.verify_shield_ad(user_id, nonce=nonce)  # abuse → ValueError
        await set_shield_ready(user_id)
        return {"ok": True, "source": "ad"}

    raise ValueError("Geçersiz kaynak (source). 'gold' veya 'ad' olmalı.")
