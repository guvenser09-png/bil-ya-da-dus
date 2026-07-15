"""Zor Mod (eski turnuva) ödül havuzu testleri.

Kapsam:
  1. compute_prize_pool: sistem seed'i (min havuz), %80 ödül / %20 sink,
     800/250/150 dağıtımı, oyuncu sayısına göre büyüme.
  2. GameEngine turnuva maçında prize_pool/prize_top3 hesaplar; normal maçta 0.
  3. grant_prize_pool ilk 3 gerçek oyuncuya havuz payını verir.
  4. Tam maç-sonu akışı: turnuva maçı havuz payını dağıtır (base ödülün üstüne),
     idempotent (aynı game_id iki kez → çift ödül yok).
  5. GET /api/tournament payload'ı prize_pool_info içerir.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.config import settings
from app.models.user import User
from app.services.game_service import GameEngine
from app.services.tournament_service import (
    TOURNAMENT_GOLD_COST,
    ZORMOD_PAYOUT_RATIOS,
    ZORMOD_PRIZE_SHARE,
    TournamentService,
    compute_prize_pool,
)
from tests.conftest import test_session_factory as session_factory


async def _mk_user(db, *, coins=1000) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        display_name="Test",
        avatar_id="default_01",
        coins=coins,
    )
    db.add(u)
    await db.flush()
    return u


# ---------------------------------------------------------------------------
# 1) compute_prize_pool
# ---------------------------------------------------------------------------

def test_pool_seed_floor_when_few_players():
    """Az oyuncu: havuz sistem seed'iyle ZORMOD_MIN_POOL'un altına düşmez."""
    min_pool = settings.ZORMOD_MIN_POOL

    # 0 oyuncu → tamamen seed.
    p0 = compute_prize_pool(0)
    assert p0["prize_pool"] == min_pool
    assert p0["entries_total"] == 0

    # 5 oyuncu × 100 = 500 < 1000 → seed devreye girer.
    p5 = compute_prize_pool(5)
    assert p5["entries_total"] == 500
    assert p5["prize_pool"] == min_pool  # seed floor


def test_pool_grows_with_players_above_floor():
    """Girişler seed'i aşınca havuz gerçek girişler toplamına eşit olur."""
    # 12 oyuncu × 100 = 1200 > 1000 → havuz 1200.
    p12 = compute_prize_pool(12)
    assert p12["entries_total"] == 12 * TOURNAMENT_GOLD_COST == 1200
    assert p12["prize_pool"] == 1200


def test_pool_80_20_split_and_distribution():
    """Havuzun %80'i ödül, %20'si yanar; dağıtım 800/250/150 oranıyla."""
    p12 = compute_prize_pool(12)  # havuz 1200
    pool = p12["prize_pool"]
    top3 = p12["prize_top3"]

    # %80 dağıtılabilir = 960; %20 = 240 sink.
    distributable = pool * ZORMOD_PRIZE_SHARE
    assert distributable == 960
    assert p12["distributable"] == 960

    # 800/250/150 → 1200 normalize.
    total_ratio = sum(ZORMOD_PAYOUT_RATIOS)
    assert top3 == [
        int(distributable * 800 / total_ratio),
        int(distributable * 250 / total_ratio),
        int(distributable * 150 / total_ratio),
    ]
    assert top3 == [640, 200, 120]

    # Ödül toplamı dağıtılabilirin (%80) İÇİNDE kalır (yuvarlama sink lehine).
    assert sum(top3) <= distributable
    # Sink en az havuzun %20'si kadar (kalan yanar).
    assert pool - sum(top3) >= pool * (1 - ZORMOD_PRIZE_SHARE)


def test_pool_min_distribution_values():
    """Seed tabanlı (1000) havuzda dağıtım: 533/166/100 (yuvarlama)."""
    p = compute_prize_pool(0)  # havuz 1000, dağıtılabilir 800
    assert p["prize_top3"] == [533, 166, 100]


# ---------------------------------------------------------------------------
# 2) GameEngine havuz hesabı
# ---------------------------------------------------------------------------

def test_engine_tournament_computes_pool():
    """Turnuva maçında engine.prize_pool/prize_top3 dolar (3 gerçek oyuncu)."""
    players = [
        {"user_id": f"u{i}", "username": f"p{i}", "display_name": f"P{i}", "avatar_id": "a"}
        for i in range(3)
    ]
    engine = GameEngine("gt", players, [], is_tournament=True)
    # 3 × 100 = 300 < 1000 → seed → havuz 1000, dağıtım 533/166/100.
    assert engine.prize_pool == 1000
    assert engine.prize_top3 == [533, 166, 100]


def test_engine_normal_match_no_pool():
    """Normal maçta havuz 0 (prize alanları boş)."""
    players = [{"user_id": "u1", "username": "p1", "display_name": "P", "avatar_id": "a"}]
    engine = GameEngine("gn", players, [])
    assert engine.prize_pool == 0
    assert engine.prize_top3 == []


# ---------------------------------------------------------------------------
# 3) grant_prize_pool
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grant_prize_pool_awards_top3(db_session):
    """İlk 3 gerçek oyuncuya havuz payı altın olarak eklenir; 4. almaz."""
    a = await _mk_user(db_session, coins=0)
    b = await _mk_user(db_session, coins=0)
    c = await _mk_user(db_session, coins=0)
    d = await _mk_user(db_session, coins=0)

    ranked = [str(a.id), str(b.id), str(c.id), str(d.id)]
    awarded = await TournamentService.grant_prize_pool(db_session, ranked, [640, 200, 120])

    assert awarded == {str(a.id): 640, str(b.id): 200, str(c.id): 120}
    assert a.coins == 640
    assert b.coins == 200
    assert c.coins == 120
    assert d.coins == 0  # ilk 3 dışında ödül yok


# ---------------------------------------------------------------------------
# 4) Tam maç-sonu akışı — turnuva havuz dağıtımı + idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_tournament_distributes_pool_idempotent(mock_redis):
    """Turnuva maç sonu: base ödül + havuz payı; ikinci çağrı çift ödül vermez."""
    async with session_factory() as db:
        w = await _mk_user(db, coins=1000)
        s = await _mk_user(db, coins=1000)
        g = await _mk_user(db, coins=0)
        await db.commit()
        w_id, s_id, g_id = str(w.id), str(s.id), str(g.id)

    players = [
        {"user_id": w_id, "username": "pw", "display_name": "W", "avatar_id": "a"},
        {"user_id": s_id, "username": "ps", "display_name": "S", "avatar_id": "a"},
        {"user_id": g_id, "username": "pg", "display_name": "G", "avatar_id": "a"},
    ]
    engine = GameEngine("g_tour", players, [], is_tournament=True)
    # Havuz: 3 gerçek → seed 1000 → paylar 533/166/100.
    assert engine.prize_top3 == [533, 166, 100]
    engine.players["pw"].score = 300
    engine.players["ps"].score = 200
    engine.players["pg"].score = 100

    final = {"winner": {"username": "pw"}, "leaderboard": [], "total_rounds": 5}

    from app.ws.game import _persist_game_results

    with patch("app.ws.game.async_session_factory", session_factory), \
         patch("app.ws.game.get_redis", AsyncMock(return_value=mock_redis)):
        coins1, prizes1 = await _persist_game_results("g_tour", engine, final)
        coins2, prizes2 = await _persist_game_results("g_tour", engine, final)

    # Base maç ödülü (30/15/15) + havuz payı (533/166/100).
    assert coins1 == {w_id: 30, s_id: 15, g_id: 15}
    assert prizes1 == {w_id: 533, s_id: 166, g_id: 100}
    # İkinci çağrı: idempotent.
    assert coins2 == {}
    assert prizes2 == {}

    async with session_factory() as db:
        w2 = (await db.execute(select(User).where(User.id == uuid.UUID(w_id)))).scalar_one()
        s2 = (await db.execute(select(User).where(User.id == uuid.UUID(s_id)))).scalar_one()
        g2 = (await db.execute(select(User).where(User.id == uuid.UUID(g_id)))).scalar_one()
    assert w2.coins == 1000 + 30 + 533   # base + havuz
    assert s2.coins == 1000 + 15 + 166
    assert g2.coins == 0 + 15 + 100


# ---------------------------------------------------------------------------
# 5) info payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tournament_info_has_prize_pool_info(db_session):
    """GET tournament info prize_pool_info (min/max havuz + oranlar) içerir."""
    u = await _mk_user(db_session, coins=500)
    info = await TournamentService.info(db_session, str(u.id))

    assert "prize_pool_info" in info
    ppi = info["prize_pool_info"]
    assert ppi["entry_cost"] == TOURNAMENT_GOLD_COST
    assert ppi["min_pool"] == settings.ZORMOD_MIN_POOL
    assert ppi["prize_share"] == ZORMOD_PRIZE_SHARE
    assert ppi["sink_share"] == round(1 - ZORMOD_PRIZE_SHARE, 2)
    assert ppi["payout_ratios"] == list(ZORMOD_PAYOUT_RATIOS)
    # Garanti minimum havuz dağıtımı.
    assert ppi["prize_pool"] == settings.ZORMOD_MIN_POOL
    assert ppi["prize_top3"] == [533, 166, 100]
    # Dolu lobi (MAX_PLAYERS) senaryosu.
    assert ppi["max_prize_pool"] == settings.MAX_PLAYERS * TOURNAMENT_GOLD_COST
