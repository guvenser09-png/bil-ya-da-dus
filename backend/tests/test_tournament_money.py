"""Denetim doğrulama testleri — turnuva para güvenliği + 3x puan + REST result.

Kapsam:
  1. Turnuva maçında ranked sezon puanı 3x yazılıyor.
  2. Maç hiç başlamazsa turnuva giriş ücreti İADE ediliyor.
  3. Çift /enter tek altın düşürüyor (idempotency).
  4. REST my_result yeni alanları (xp_gained, total_rounds, final_round) içeriyor.
"""

import pytest

from app.models.user import User
from app.services.tournament_service import (
    TOURNAMENT_GOLD_COST,
    TOURNAMENT_POINT_MULTIPLIER,
    TournamentService,
)
from app.utils.season_util import season_id_for


async def _make_user(db, *, coins=10000) -> User:
    import uuid

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


@pytest.mark.asyncio
async def test_tournament_3x_season_points(db_session):
    """Turnuva çarpanı uygulanınca ranked puan normal maçın 3 katı olmalı."""
    u_normal = await _make_user(db_session)
    u_tour = await _make_user(db_session)
    base = 100

    await TournamentService.add_season_points(db_session, str(u_normal.id), base)
    await TournamentService.add_season_points(
        db_session, str(u_tour.id), base * TOURNAMENT_POINT_MULTIPLIER
    )
    await db_session.flush()

    sid = season_id_for()
    from sqlalchemy import select

    from app.models.tournament import SeasonScore

    normal = (
        await db_session.execute(
            select(SeasonScore.points).where(
                SeasonScore.user_id == u_normal.id, SeasonScore.season_id == sid
            )
        )
    ).scalar_one()
    tour = (
        await db_session.execute(
            select(SeasonScore.points).where(
                SeasonScore.user_id == u_tour.id, SeasonScore.season_id == sid
            )
        )
    ).scalar_one()

    assert tour == normal * TOURNAMENT_POINT_MULTIPLIER == 300


@pytest.mark.asyncio
async def test_enter_creates_ticket_and_refund(db_session):
    """Giriş bilet açar; maç başlamazsa iade altını geri verir (idempotent)."""
    u = await _make_user(db_session, coins=1000)
    before = u.coins

    res = await TournamentService.enter(db_session, str(u.id), "gold")
    await db_session.flush()
    assert res["entered"] is True
    assert res["reused"] is False
    assert u.coins == before - TOURNAMENT_GOLD_COST

    ticket = await TournamentService.get_pending_ticket(str(u.id))
    assert ticket is not None and ticket["status"] == "pending"

    # Maç başlamadı → iade
    refunded = await TournamentService.refund_ticket(db_session, str(u.id))
    await db_session.flush()
    assert refunded is True
    assert u.coins == before  # altın geri geldi

    # İkinci iade no-op (idempotent) — çift iade yok
    refunded2 = await TournamentService.refund_ticket(db_session, str(u.id))
    assert refunded2 is False
    assert u.coins == before


@pytest.mark.asyncio
async def test_double_enter_single_charge(db_session):
    """Çift /enter tek altın düşürmeli (idempotency)."""
    u = await _make_user(db_session, coins=1000)
    before = u.coins

    r1 = await TournamentService.enter(db_session, str(u.id), "gold")
    await db_session.flush()
    r2 = await TournamentService.enter(db_session, str(u.id), "gold")
    await db_session.flush()

    assert r1["reused"] is False
    assert r2["reused"] is True
    # Sadece BİR kez düşmeli
    assert u.coins == before - TOURNAMENT_GOLD_COST


@pytest.mark.asyncio
async def test_consume_blocks_refund(db_session):
    """Maç başlayıp bilet tüketilince artık iade YAPILMAMALI (altın sink)."""
    u = await _make_user(db_session, coins=1000)
    before = u.coins

    await TournamentService.enter(db_session, str(u.id), "gold")
    await db_session.flush()
    await TournamentService.consume_ticket(str(u.id))

    # Tüketilmiş bilet pending değil → iade no-op
    assert await TournamentService.get_pending_ticket(str(u.id)) is None
    refunded = await TournamentService.refund_ticket(db_session, str(u.id))
    await db_session.flush()
    assert refunded is False
    assert u.coins == before - TOURNAMENT_GOLD_COST  # yandı (sink), geri gelmedi


@pytest.mark.asyncio
async def test_sweeper_refunds_orphan_pending(db_session, mock_redis):
    """>10 dk pending kalmış (hiç bağlanmamış) yetim bilet süpürücüyle iade edilir."""
    import time
    from unittest.mock import patch

    from tests.conftest import test_session_factory

    u = await _make_user(db_session, coins=1000)
    before = u.coins

    await TournamentService.enter(db_session, str(u.id), "gold")
    await db_session.commit()  # sweeper kendi session'ında kullanıcıyı okuyabilsin
    assert u.coins == before - TOURNAMENT_GOLD_COST

    # Bileti ve index skorunu "11 dk önce oluşmuş" gibi geriye al.
    old_ts = time.time() - 660
    ticket = await TournamentService.get_pending_ticket(str(u.id))
    ticket["created_at"] = old_ts
    await TournamentService._write_ticket(str(u.id), ticket, 3600)
    await mock_redis.zadd("tournament:tickets:pending", {str(u.id): old_ts})

    # Sweeper kendi session'ını test DB'sinden açsın.
    with patch("app.database.async_session_factory", test_session_factory):
        # Süpür → iade edilmeli (1 bilet).
        n = await TournamentService.sweep_orphan_tickets()
        assert n == 1

        await db_session.refresh(u)
        assert u.coins == before  # altın geri geldi
        # Bilet artık pending değil → ikinci süpürme çift iade yapmaz (idempotent).
        n2 = await TournamentService.sweep_orphan_tickets()
        assert n2 == 0
        await db_session.refresh(u)
        assert u.coins == before


@pytest.mark.asyncio
async def test_sweeper_skips_recent_and_consumed(db_session, mock_redis):
    """Yeni (10 dk dolmamış) ve consumed biletler süpürücüyle İADE EDİLMEZ."""
    from unittest.mock import patch

    from tests.conftest import test_session_factory

    # 1) Yeni pending bilet → henüz yetim değil, iade edilmez.
    u_new = await _make_user(db_session, coins=1000)
    before_new = u_new.coins
    await TournamentService.enter(db_session, str(u_new.id), "gold")

    # 2) Consume edilmiş bilet → index'ten çıkmış olmalı, iade edilmez.
    u_done = await _make_user(db_session, coins=1000)
    before_done = u_done.coins
    await TournamentService.enter(db_session, str(u_done.id), "gold")
    await TournamentService.consume_ticket(str(u_done.id))
    # consume edilmiş bileti yaşlandırsak bile index'te olmadığı için süpürülmez.
    await db_session.commit()

    with patch("app.database.async_session_factory", test_session_factory):
        n = await TournamentService.sweep_orphan_tickets()
    assert n == 0

    await db_session.refresh(u_new)
    await db_session.refresh(u_done)
    assert u_new.coins == before_new - TOURNAMENT_GOLD_COST   # hâlâ pending (yeni)
    assert u_done.coins == before_done - TOURNAMENT_GOLD_COST  # consumed → sink


def test_rest_my_result_new_fields():
    """REST my_result xp_gained/total_rounds/final_round içermeli."""
    from app.api.games import _result_from_leaderboard

    uid = "user-123"
    leaderboard = [
        {
            "user_id": uid,
            "username": "alice",
            "display_name": "Alice",
            "avatar_id": "default_01",
            "score": 420,
            "correct_answers": 4,
            "rounds_survived": 5,
            "is_winner": True,
            "coins_earned": 50,
        },
    ]
    out = _result_from_leaderboard(leaderboard, "alice", uid, total_rounds=5)
    assert out is not None
    mr = out["my_result"]
    assert mr["xp_gained"] == 420
    assert mr["total_rounds"] == 5
    assert mr["final_round"] == 5
    assert mr["score"] == 420
    assert out["total_rounds"] == 5
