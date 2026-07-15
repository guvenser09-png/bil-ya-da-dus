"""Zor Mod (eski turnuva) SABİT ödül testleri.

Kapsam:
  1. compute_prize_pool: SABİT ödüller (1. 700 / 2. 300 / 3. 200); oyuncu
     sayısına/girişlere BAĞLI DEĞİL. prize_pool = payların toplamı (1200).
  2. GameEngine turnuva maçında prize_pool/prize_top3 SABİT hesaplar; normal
     maçta 0.
  3. grant_prize_pool ilk 3 gerçek oyuncuya sabit payı verir; 4. almaz.
  4. Tam maç-sonu akışı: Zor Mod maçı YALNIZCA havuz payını dağıtır (normal
     30/15/5 maç ödülü VERİLMEZ — "tek ödül"); idempotent.
  5. GET /api/tournament payload'ı sabit prize_pool_info içerir.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.user import User
from app.services.game_service import GameEngine
from app.services.tournament_service import (
    TOURNAMENT_GOLD_COST,
    ZORMOD_FIXED_PRIZES,
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
# 1) compute_prize_pool — SABİT
# ---------------------------------------------------------------------------

def test_prizes_are_fixed_700_300_200():
    """Ödüller sabit: 1. 700 / 2. 300 / 3. 200; havuz = toplam (1200)."""
    assert ZORMOD_FIXED_PRIZES == (700, 300, 200)
    p = compute_prize_pool(0)
    assert p["prize_top3"] == [700, 300, 200]
    assert p["prize_pool"] == 1200
    assert p["distributable"] == 1200


def test_prizes_independent_of_player_count():
    """Oyuncu sayısı ödülü DEĞİŞTİRMEZ (sadece entries_total bilgi amaçlı)."""
    p0 = compute_prize_pool(0)
    p5 = compute_prize_pool(5)
    p12 = compute_prize_pool(12)

    # Ödüller her senaryoda aynı (sabit).
    for p in (p0, p5, p12):
        assert p["prize_pool"] == 1200
        assert p["prize_top3"] == [700, 300, 200]

    # entries_total yalnızca girişlerin topladığı (bilgi amaçlı) — ödülü etkilemez.
    assert p0["entries_total"] == 0
    assert p5["entries_total"] == 5 * TOURNAMENT_GOLD_COST == 500
    assert p12["entries_total"] == 12 * TOURNAMENT_GOLD_COST == 1200


# ---------------------------------------------------------------------------
# 2) GameEngine havuz hesabı
# ---------------------------------------------------------------------------

def test_engine_tournament_computes_fixed_pool():
    """Turnuva maçında engine.prize_pool/prize_top3 SABİT dolar."""
    players = [
        {"user_id": f"u{i}", "username": f"p{i}", "display_name": f"P{i}", "avatar_id": "a"}
        for i in range(3)
    ]
    engine = GameEngine("gt", players, [], is_tournament=True)
    assert engine.prize_pool == 1200
    assert engine.prize_top3 == [700, 300, 200]


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
    """İlk 3 gerçek oyuncuya sabit pay altın olarak eklenir; 4. almaz."""
    a = await _mk_user(db_session, coins=0)
    b = await _mk_user(db_session, coins=0)
    c = await _mk_user(db_session, coins=0)
    d = await _mk_user(db_session, coins=0)

    ranked = [str(a.id), str(b.id), str(c.id), str(d.id)]
    awarded = await TournamentService.grant_prize_pool(db_session, ranked, [700, 300, 200])

    assert awarded == {str(a.id): 700, str(b.id): 300, str(c.id): 200}
    assert a.coins == 700
    assert b.coins == 300
    assert c.coins == 200
    assert d.coins == 0  # ilk 3 dışında ödül yok


# ---------------------------------------------------------------------------
# 4) Tam maç-sonu akışı — Zor Mod SADECE havuz payı (tek ödül) + idempotency
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_persist_tournament_only_pool_no_base_reward(mock_redis):
    """Zor Mod maç sonu: SADECE havuz payı (normal 30/15/5 YOK); idempotent."""
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
    # Sabit ödül: 700/300/200.
    assert engine.prize_top3 == [700, 300, 200]
    engine.players["pw"].score = 300
    engine.players["ps"].score = 200
    engine.players["pg"].score = 100

    final = {"winner": {"username": "pw"}, "leaderboard": [], "total_rounds": 5}

    from app.ws.game import _persist_game_results

    with patch("app.ws.game.async_session_factory", session_factory), \
         patch("app.ws.game.get_redis", AsyncMock(return_value=mock_redis)):
        coins1, prizes1 = await _persist_game_results("g_tour", engine, final)
        coins2, prizes2 = await _persist_game_results("g_tour", engine, final)

    # Zor Mod'da NORMAL maç ödülü verilmez → coins boş; tek ödül havuz payı.
    assert coins1 == {}
    assert prizes1 == {w_id: 700, s_id: 300, g_id: 200}
    # İkinci çağrı: idempotent.
    assert coins2 == {}
    assert prizes2 == {}

    async with session_factory() as db:
        w2 = (await db.execute(select(User).where(User.id == uuid.UUID(w_id)))).scalar_one()
        s2 = (await db.execute(select(User).where(User.id == uuid.UUID(s_id)))).scalar_one()
        g2 = (await db.execute(select(User).where(User.id == uuid.UUID(g_id)))).scalar_one()
    # Yalnızca sabit havuz payı eklenir (base 30/15/5 YOK).
    assert w2.coins == 1000 + 700
    assert s2.coins == 1000 + 300
    assert g2.coins == 0 + 200


# ---------------------------------------------------------------------------
# 5) info payload
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_tournament_info_has_fixed_prize_pool_info(db_session):
    """GET tournament info sabit prize_pool_info (1200 + [700,300,200]) içerir."""
    u = await _mk_user(db_session, coins=500)
    info = await TournamentService.info(db_session, str(u.id))

    assert "prize_pool_info" in info
    ppi = info["prize_pool_info"]
    assert ppi["entry_cost"] == TOURNAMENT_GOLD_COST
    assert ppi["fixed"] is True
    assert ppi["prize_pool"] == 1200
    assert ppi["prize_top3"] == [700, 300, 200]

    # Mobil top-level sözleşmesi de sabit değerleri yansıtır.
    assert info["prize_pool"] == 1200
    assert info["prize_top3"] == [700, 300, 200]
