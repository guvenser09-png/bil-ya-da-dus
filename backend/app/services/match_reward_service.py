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
from app.services.user_service import UserService

logger = logging.getLogger("app.match_reward")

# Ödül miktarları.
REWARD_WINNER = 50
REWARD_TOP3 = 25
REWARD_PARTICIPATION = 10

# Günlük maç-ödülü cap'i (anti-farm).
MATCH_REWARD_DAILY_CAP = 500

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
    now: datetime | None = None,
) -> dict[str, int]:
    """Sıralı GERÇEK oyuncu listesine maç ödülünü uygula (cap'li, sadece coin).

    Args:
        db: Aktif async session (commit ÇAĞIRAN tarafça yapılır).
        ranked_user_ids: Skora göre AZALAN sırada GERÇEK oyuncu id'leri
            (bot ve user_id'siz oyuncular ÇAĞIRAN tarafça çıkarılmış olmalı).
        now: Test edilebilirlik için zaman enjeksiyonu.

    Returns:
        {user_id: kazanılan_coin} haritası (cap sonrası gerçek miktar).
    """
    now = now or datetime.now(timezone.utc)
    earned: dict[str, int] = {}

    for idx, uid in enumerate(ranked_user_ids):
        rank = idx + 1
        raw = reward_for_rank(rank)
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

    return earned
