"""Ekonomi kıtlaştırması — sabit sayı denetimleri (önce/sonra).

Bu dosya, kararların BİREBİR uygulandığını sabitleyen "guard" testlerdir:
  - Başlangıç altını 300.
  - Maç ödülü 15/8/2 (2. kıtlaştırma turu); günlük cap 500 KALIR.
  - Şampiyon bahsi ödülü 15 (kazanan ödülüyle hizalı).
  - Sezon tier eşiği 1000 (puan-başı altın ~%80 düşer).
  - Ödüllü reklam "gold" yerleşimi +100 (mağaza gösterimiyle BİREBİR aynı).
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
    """Maç ödülü (2. kıtlaştırma): kazanan 15, 2.-3. 8, katılım 2; cap 500 KALIR."""
    from app.services import match_reward_service as mr

    assert mr.REWARD_WINNER == 15
    assert mr.REWARD_TOP3 == 8
    assert mr.REWARD_PARTICIPATION == 2
    assert mr.MATCH_REWARD_DAILY_CAP == 500  # değişmedi

    # reward_for_rank sözleşmesi.
    assert mr.reward_for_rank(1) == 15
    assert mr.reward_for_rank(2) == 8
    assert mr.reward_for_rank(3) == 8
    assert mr.reward_for_rank(4) == 2
    assert mr.reward_for_rank(12) == 2


def test_champion_bet_reward_is_15():
    """Şampiyon bahsi ödülü 25 → 15: kazanan ödülünü (15) AŞMAZ."""
    from app.services import match_reward_service as mr

    assert mr.BET_REWARD == 15
    # Bahsi tutturmak, maçı kazanmaktan (REWARD_WINNER) daha çok altın vermemeli.
    assert mr.BET_REWARD <= mr.REWARD_WINNER


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


def test_ads_gold_placement_gives_100():
    """Ödüllü reklam 'gold' yerleşimi +100 altın; günlük cap deseni korunur.

    TUTARLILIK: bu değer, mağazada GÖSTERİLEN miktarla (store_screen.dart
    "+100 altın") BİREBİR aynı olmak zorunda — eski 200↔100 tutarsızlığı ve
    "ilk sefer 2 katı" bug'ı bu birebirlik + nonce idempotency ile kapandı.
    """
    from app.services.ads_service import ADS_DAILY_LIMIT, PLACEMENTS

    assert "gold" in PLACEMENTS
    assert PLACEMENTS["gold"]["reward"] == {"coins": 100}
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
    # 490 zaten verildiyse, 15'lik ödülden yalnızca 10 verilir (cap 500).
    u.match_reward_coins_today = 490
    u.match_reward_date = now.astimezone(timezone.utc).strftime("%Y-%m-%d")
    granted = _apply_daily_cap(u, 15, now)
    assert granted == 10
    assert u.match_reward_coins_today == 500
    # Cap dolduktan sonra sıfır verilir.
    assert _apply_daily_cap(u, 15, now) == 0


@pytest.mark.asyncio
async def test_ad_gold_reward_consistent_and_idempotent(db_session):
    """GÖREV 1 regresyonu — ödüllü reklam 'gold' TUTARLI +100 verir, çift-grant YOK.

    "İlk seferinde 200 verdi sonra 100'e düştü" bug'ının kök nedeni: gold POST'u
    nonce GÖNDERMİYORDU → backend idempotency guard'ı (Redis SET NX) atlanıyor,
    tekrar giden istek (auth-interceptor 401→retry / ağ tekrarı) ödülü İKİNCİ kez
    veriyordu. Artık istemci her izleme için nonce üretir. Bu test doğrular:
      - Her başarılı grant TAM +100 (ilk-sefer 2x YOK).
      - Aynı nonce ikinci kez → ValueError, altın ARTMAZ (idempotency).
      - Farklı nonce → normal +100 daha.
    """
    import uuid

    from app.services.ads_service import PLACEMENTS, AdsService

    assert PLACEMENTS["gold"]["reward"]["coins"] == 100  # gösterimle birebir

    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        coins=0,
    )
    db_session.add(u)
    await db_session.flush()
    uid = str(u.id)

    # 1) İlk izleme → tam +100 (2 KATI DEĞİL).
    res1 = await AdsService.grant_reward(db_session, uid, "gold", nonce="nonce-1")
    assert res1["reward"]["coins"] == 100
    assert u.coins == 100

    # 2) AYNI nonce tekrar → idempotency: reddedilir, altın ARTMAZ.
    with pytest.raises(ValueError):
        await AdsService.grant_reward(db_session, uid, "gold", nonce="nonce-1")
    assert u.coins == 100

    # 3) FARKLI nonce → normal +100 daha (yine tam 100, ilk-sefer bonusu yok).
    res3 = await AdsService.grant_reward(db_session, uid, "gold", nonce="nonce-2")
    assert res3["reward"]["coins"] == 100
    assert u.coins == 200
