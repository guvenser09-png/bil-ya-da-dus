"""Ekonomi kıtlaştırması — sabit sayı denetimleri (önce/sonra).

Bu dosya, kararların BİREBİR uygulandığını sabitleyen "guard" testlerdir:
  - Başlangıç altını 300.
  - Maç ödülü 30/15/5; günlük cap 500 KALIR.
  - Sezon tier eşiği 1000 (puan-başı altın ~%80 düşer).
  - Ödüllü reklam "gold" yerleşimi +200.
  - Zor Mod (turnuva) girişi 100.
"""

import pytest

from app.models.user import User


def test_starting_coins_is_300():
    """Yeni oyuncu başlangıç altını 300 (1000'den kıtlaştırıldı)."""
    # SQLAlchemy kolon default'u doğrudan model üzerinden okunur.
    default = User.__table__.c.coins.default.arg
    assert default == 300


def test_match_reward_amounts():
    """Maç ödülü: kazanan 30, 2.-3. 15, katılım 5; günlük cap 500 KALIR."""
    from app.services import match_reward_service as mr

    assert mr.REWARD_WINNER == 30
    assert mr.REWARD_TOP3 == 15
    assert mr.REWARD_PARTICIPATION == 5
    assert mr.MATCH_REWARD_DAILY_CAP == 500  # değişmedi

    # reward_for_rank sözleşmesi.
    assert mr.reward_for_rank(1) == 30
    assert mr.reward_for_rank(2) == 15
    assert mr.reward_for_rank(3) == 15
    assert mr.reward_for_rank(4) == 5
    assert mr.reward_for_rank(12) == 5


def test_shield_billing_removed():
    """Eski kalkan bedeli mantığı tamamen kaldırıldı."""
    from app.services import match_reward_service as mr

    assert not hasattr(mr, "SHIELD_COST")
    assert not hasattr(mr, "charge_shield_costs")


def test_season_points_per_tier_is_1000():
    """Sezon tier eşiği 200 → 1000; ödül yapısı korunur (yalnızca hız ölçeklenir)."""
    from app.services.season_service import (
        POINTS_PER_TIER,
        SEASON_TIERS_TABLE,
        SeasonService,
    )

    assert POINTS_PER_TIER == 1000

    # Tier i, i*1000 puan gerektirir; ödül miktarları AYNI kaldı (100/250/500).
    t1 = SEASON_TIERS_TABLE[0]
    assert t1["tier"] == 1
    assert t1["points_required"] == 1000
    assert t1["free_reward"] == {"type": "coins", "amount": 100}

    t5 = SEASON_TIERS_TABLE[4]
    assert t5["points_required"] == 5000
    assert t5["free_reward"] == {"type": "coins", "amount": 250}

    t10 = SEASON_TIERS_TABLE[9]
    assert t10["points_required"] == 10000
    assert t10["free_reward"] == {"type": "coins", "amount": 500}

    # calculate_tier eşiklerle tutarlı.
    assert SeasonService.calculate_tier(999) == 0
    assert SeasonService.calculate_tier(1000) == 1
    assert SeasonService.calculate_tier(4999) == 4
    assert SeasonService.calculate_tier(5000) == 5


def test_ads_gold_placement_gives_200():
    """Ödüllü reklam 'gold' yerleşimi +200 altın; günlük cap deseni korunur."""
    from app.services.ads_service import ADS_DAILY_LIMIT, PLACEMENTS

    assert "gold" in PLACEMENTS
    assert PLACEMENTS["gold"]["reward"] == {"coins": 200}
    # Kötüye kullanım sınırı (placement başına günlük cap) tanımlı.
    assert PLACEMENTS["gold"]["daily_cap"] >= 1
    # Genel günlük toplam limit hâlâ mevcut (mevcut cap deseni korundu).
    assert ADS_DAILY_LIMIT == 5


def test_tournament_entry_cost_is_100():
    """Zor Mod (turnuva) girişi 150 → 100 altın; 3x çarpan ve zor havuz korunur."""
    from app.services.tournament_service import (
        TOURNAMENT_GOLD_COST,
        TOURNAMENT_MIN_DIFFICULTY,
        TOURNAMENT_POINT_MULTIPLIER,
    )

    assert TOURNAMENT_GOLD_COST == 100
    assert TOURNAMENT_POINT_MULTIPLIER == 3   # değişmedi
    assert TOURNAMENT_MIN_DIFFICULTY == 4     # zor soru filtresi korundu


@pytest.mark.asyncio
async def test_daily_cap_still_500_on_match_reward(db_session):
    """Maç ödülü günlük 500 cap'i KALIR: cap'i aşan miktar verilmez."""
    import uuid

    from app.services.match_reward_service import _apply_daily_cap
    from datetime import datetime, timezone

    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        coins=0,
    )
    db_session.add(u)
    await db_session.flush()

    now = datetime.now(timezone.utc)
    # 490 zaten verildiyse, 30'luk ödülden yalnızca 10 verilir (cap 500).
    u.match_reward_coins_today = 490
    u.match_reward_date = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    granted = _apply_daily_cap(u, 30, now)
    assert granted == 10
    assert u.match_reward_coins_today == 500
    # Cap dolduktan sonra sıfır verilir.
    assert _apply_daily_cap(u, 30, now) == 0
