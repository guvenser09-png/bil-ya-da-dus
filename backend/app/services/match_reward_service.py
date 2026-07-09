"""Maç sonu coin ödülü servisi (pay-to-win YOK).

Maç bitişinde GERÇEK oyunculara yalnızca COIN ödülü verir. Coin pay-to-win
değildir — oyun içi bilgi/avantaj (kolay soru, ekstra süre, joker, kalıcı puan)
ASLA satılmaz veya ödüllendirilmez. Coin sadece kozmetik almak için kullanılır.

Ödül tablosu (sıralamaya göre):
  - Kazanan (1.):           +50 coin
  - İlk 3 (2.-3.):          +25 coin
  - Oynayan herkes (taban): +10 coin

Anti-farm: kullanıcı başına maç ödülünden GÜNLÜK en fazla MATCH_REWARD_DAILY_CAP
coin verilir. Cap takibi User.match_reward_date / match_reward_coins_today
alanlarında UTC gün bazlı tutulur.

İdempotency: aynı maç iki kez ödüllendirilmesin diye Redis'te işlenen
(game_id) anahtarı tutulur; Redis yoksa best-effort devam eder (çağıran taraf
zaten maç başına bir kez çağırır).
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.services import anti_tilt_service
from app.services.user_service import UserService

logger = logging.getLogger("app.match_reward")

# Ödül miktarları.
REWARD_WINNER = 50
REWARD_TOP3 = 25
REWARD_PARTICIPATION = 10

# Günlük maç-ödülü cap'i (anti-farm).
MATCH_REWARD_DAILY_CAP = 500

# --- Hayalet modu (👻) altını ---
# Elenen oyuncu izlerken cevap vermeye devam eder; doğru başına küçük altın.
# Üst sınır: en erken (1. turda) elenen oyuncu en fazla 4 tur daha cevaplar.
GHOST_GOLD_PER_CORRECT = 5
GHOST_GOLD_MAX = 20

# --- Şampiyon bahsi (🎯) ödülü ---
# Elenen oyuncu hayatta kalanlardan birine tek seferlik bahis koyar; şampiyonu
# tutturursa maç sonunda bu altını alır (günlük cap'e DAHİL).
BET_REWARD = 25


def ghost_reward_for(correct_count: int) -> int:
    """Hayalet doğru sayısını altına çevir (doğru başına +5, üst sınır 20)."""
    return min(max(0, int(correct_count)) * GHOST_GOLD_PER_CORRECT, GHOST_GOLD_MAX)

# --- Maç sonu XP (seviye sistemi) ---
# Katılım + hayatta kalınan tur başına + galibiyet. XP satın alınamaz, sadece
# oynayarak kazanılır; user_service.calculate_level eğrisiyle seviyeye çevrilir.
XP_PARTICIPATION = 20
XP_PER_ROUND_SURVIVED = 10
XP_WIN = 50

# Redis idempotency anahtarı TTL (saniye) — 1 gün yeterli.
_IDEMPOTENCY_TTL = 24 * 3600


def reward_for_rank(rank: int) -> int:
    """Sıralamaya (1 tabanlı) göre ham coin ödülünü döndür.

    rank 1 -> winner, rank 2-3 -> top3, diğer -> participation.
    """
    if rank <= 0:
        return REWARD_PARTICIPATION
    if rank == 1:
        return REWARD_WINNER
    if rank <= 3:
        return REWARD_TOP3
    return REWARD_PARTICIPATION


def _utc_day(now: datetime) -> str:
    return now.astimezone(timezone.utc).strftime("%Y-%m-%d")


def _apply_daily_cap(user: User, raw_reward: int, now: datetime) -> int:
    """Günlük cap'i uygula ve kullanıcı sayaçlarını güncelle.

    Returns:
        Cap sonrası gerçekten verilecek coin miktarı (0..raw_reward).
    """
    today = _utc_day(now)
    if user.match_reward_date != today:
        # Gün değişti → sayaç sıfırla.
        user.match_reward_date = today
        user.match_reward_coins_today = 0

    already = user.match_reward_coins_today or 0
    remaining = MATCH_REWARD_DAILY_CAP - already
    if remaining <= 0:
        return 0
    grant = min(raw_reward, remaining)
    user.match_reward_coins_today = already + grant
    return grant


async def grant_match_rewards(
    db: AsyncSession,
    ranked_user_ids: list[str],
    *,
    bonuses: dict[str, int] | None = None,
    now: datetime | None = None,
) -> dict[str, int]:
    """Sıralı GERÇEK oyuncu listesine maç ödülünü uygula (cap'li, sadece coin).

    Args:
        db: Aktif async session (commit ÇAĞIRAN tarafça yapılır).
        ranked_user_ids: Skora göre AZALAN sırada GERÇEK oyuncu id'leri
            (bot ve user_id'siz oyuncular ÇAĞIRAN tarafça çıkarılmış olmalı).
        bonuses: Kişi bazlı EK altın ({user_id: miktar}) — hayalet modu
            doğruları + tutan şampiyon bahsi. Sıralama ödülüyle AYNI cap
            havuzuna dahil edilir (anti-farm bütünlüğü korunur).
        now: Test edilebilirlik için zaman enjeksiyonu.

    Returns:
        {user_id: kazanılan_coin} haritası (cap sonrası gerçek miktar).
    """
    now = now or datetime.now(timezone.utc)
    bonuses = bonuses or {}
    earned: dict[str, int] = {}

    for idx, uid in enumerate(ranked_user_ids):
        rank = idx + 1
        raw = reward_for_rank(rank) + max(0, int(bonuses.get(uid, 0)))
        try:
            user = await UserService.get_user_by_id(db, uid)
            if not user:
                continue
            granted = _apply_daily_cap(user, raw, now)
            if granted > 0:
                user.coins = (user.coins or 0) + granted
            earned[uid] = granted
        except Exception as exc:  # tek oyuncu hatası diğerlerini engellemesin
            logger.warning("Maç ödülü verilemedi (user %s): %s", uid, exc)
            earned[uid] = 0

        # Anti-tilt: maç sonucunu kaydet (1. sıradaki kazanan sayılır).
        # Ödül akışı maç başına TEK kez çalıştığı (Redis idempotency çağıran
        # tarafta) için burada güvenli; record_game_result kendi hatasını
        # yutar, coin ödülünü asla engellemez.
        await anti_tilt_service.record_game_result(uid, won=(rank == 1))

    return earned


async def grant_match_xp(
    db: AsyncSession,
    players: list[dict],
) -> dict[str, int]:
    """Maç sonunda GERÇEK oyunculara XP ver (katılım + tur + galibiyet).

    Coin ödülüyle aynı idempotent akışta (maç başına tek kez) çağrılır.

    Args:
        db: Aktif async session (commit ÇAĞIRAN tarafça yapılır).
        players: Her biri {"user_id": str, "rounds_survived": int, "won": bool}
            olan GERÇEK oyuncu listesi (botlar çağıran tarafça çıkarılmış).

    Returns:
        {user_id: verilen_xp} haritası.
    """
    granted: dict[str, int] = {}
    for p in players:
        uid = p.get("user_id")
        if not uid:
            continue
        xp = (
            XP_PARTICIPATION
            + XP_PER_ROUND_SURVIVED * max(0, int(p.get("rounds_survived") or 0))
            + (XP_WIN if p.get("won") else 0)
        )
        try:
            await UserService.add_xp(db, uid, xp)
            granted[uid] = xp
        except Exception as exc:  # tek oyuncu hatası diğerlerini engellemesin
            logger.warning("Maç XP'si verilemedi (user %s): %s", uid, exc)
            granted[uid] = 0
    return granted
