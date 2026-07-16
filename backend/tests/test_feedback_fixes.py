"""Kullanıcı test geri bildirimi düzeltmelerinin testleri.

Kapsam:
  1. KALKAN İŞARETİ + MAÇ ÖDÜLÜ: kalkan kırılınca artık EK ÜCRET YOK (eski 50
     altın bedeli kaldırıldı). Maç ödülü kıtlaştırılmış tablodan (30/15/5) verilir,
     idempotent; bot muaf.
  2. FİNAL TAHMİN ZOR HAVUZ: normal maçta 5. tur (tahmin) sorusu önce
     difficulty>=4, yoksa 3, yoksa mevcut kolay-havuz davranışıyla seçilir.
  3. MİSAFİR FİLTRESİ: is_guest=True kullanıcılar liderlik tablolarında
     listelenmez; kendi sorgularında guest_hidden=true döner.
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from sqlalchemy import select

from app.models.question import ApprovalStatus, Question, QuestionType
from app.models.user import User
from app.services.game_service import GameEngine
from tests.conftest import test_session_factory as session_factory


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

async def _mk_user(db, *, coins=1000, is_guest=False, total_score=0, games_played=1) -> User:
    u = User(
        id=uuid.uuid4(),
        username=f"u_{uuid.uuid4().hex[:8]}",
        email=f"{uuid.uuid4().hex[:8]}@t.co",
        password_hash="x",
        display_name="Test",
        avatar_id="default_01",
        coins=coins,
        is_guest=is_guest,
        total_score=total_score,
        games_played=games_played,
    )
    db.add(u)
    await db.flush()
    return u


def _mk_q(qid: str, qtype: QuestionType, difficulty: int) -> Question:
    q = Question(
        id=qid,
        type=qtype,
        category="Genel Kültür",
        difficulty=difficulty,
        content=f"Soru {qid}?",
        options=None if qtype == QuestionType.TAHMIN else ["A", "B"],
        correct_answer=None if qtype == QuestionType.TAHMIN else 0,
        approval_status=ApprovalStatus.APPROVED,
        min_value=0 if qtype == QuestionType.TAHMIN else None,
        max_value=100 if qtype == QuestionType.TAHMIN else None,
        real_answer=42 if qtype == QuestionType.TAHMIN else None,
    )
    return q


# ---------------------------------------------------------------------------
# 1) Kalkan işareti + kıtlaştırılmış maç ödülü (kalkan bedeli KALDIRILDI)
# ---------------------------------------------------------------------------

class TestMatchRewardNoShieldBilling:
    """Kalkan kırılınca ek ücret YOK; maç ödülü 30/15/5, idempotent, bot muaf."""

    def test_engine_marks_shield_broken(self):
        """Kalkanla kurtulan oyuncuda shield_broken işareti konur (bilgi amaçlı)."""
        players = [
            {"user_id": "u1", "username": "p1", "display_name": "P1", "avatar_id": "a"},
            {"user_id": "u2", "username": "p2", "display_name": "P2", "avatar_id": "a"},
        ]
        bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
        engine = GameEngine("g_shield", players, bots)
        engine.start_round({"content": "Q?", "options": ["A", "B"]})
        engine.submit_answer("p1", 1, 3.0)  # yanlış → kalkan kırılır
        engine.submit_answer("p2", 0, 3.0)  # doğru
        engine.players["bot1"].current_answer = 0
        engine.players["bot1"].answer_time = 3.0

        result = engine.end_round(correct_answer=0, question={"options": ["A", "B"]})

        assert "p1" in result.shield_saved
        assert engine.players["p1"].shield_broken is True
        assert engine.players["p1"].is_alive is True  # elenmedi, kalkan kırıldı
        assert engine.players["p2"].shield_broken is False
        assert engine.players["bot1"].shield_broken is False

    @pytest.mark.asyncio
    async def test_persist_flow_rewards_only_no_shield_charge(self, mock_redis):
        """Tam akış: sadece kıtlaştırılmış ödül eklenir, kalkan bedeli YOK, idempotent.

        Kurulum: 3 gerçek oyuncu + 1 bot (normal maç → Zor Mod havuzu yok).
          - w (kazanan): +15 ödül → 1015.
          - s (2., kalkanı kırık): +8 ödül, EK BEDEL YOK → 1008.
          - g (3., kalkanı kırık, 0 altın): +8 ödül → 8 (ek ücret yok).
        İkinci çağrı (aynı game_id) hiçbir bakiyeyi değiştirmez (Redis NX kilidi).
        """
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
        bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
        engine = GameEngine("g_persist", players, bots)
        engine.players["pw"].score = 300
        engine.players["ps"].score = 200
        engine.players["ps"].shields = 0
        engine.players["ps"].shield_broken = True
        engine.players["pg"].score = 100
        engine.players["pg"].shields = 0
        engine.players["pg"].shield_broken = True
        # Botun da kalkanı kırılmış olsun → hiçbir tahsilat/ödül almamalı.
        engine.players["bot1"].shields = 0
        engine.players["bot1"].shield_broken = True

        final = {"winner": {"username": "pw"}, "leaderboard": [], "total_rounds": 5}

        from app.ws.game import _persist_game_results

        with patch("app.ws.game.async_session_factory", session_factory), \
             patch("app.ws.game.get_redis", AsyncMock(return_value=mock_redis)):
            coins1, prizes1 = await _persist_game_results("g_persist", engine, final)
            coins2, prizes2 = await _persist_game_results("g_persist", engine, final)

        # İlk çağrı: kıtlaştırılmış ödüller (15/8/8), Zor Mod havuzu yok.
        assert coins1 == {w_id: 15, s_id: 8, g_id: 8}
        assert prizes1 == {}  # normal maç → havuz payı yok
        # İkinci çağrı: idempotent — ödül tekrar işlenmez.
        assert coins2 == {}
        assert prizes2 == {}

        async with session_factory() as db:
            w2 = (await db.execute(select(User).where(User.id == uuid.UUID(w_id)))).scalar_one()
            s2 = (await db.execute(select(User).where(User.id == uuid.UUID(s_id)))).scalar_one()
            g2 = (await db.execute(select(User).where(User.id == uuid.UUID(g_id)))).scalar_one()
        assert w2.coins == 1015   # +15 ödül
        assert s2.coins == 1008   # +8 ödül, kalkan bedeli YOK (eskiden -50 idi)
        assert g2.coins == 8      # +8 ödül, ek ücret yok


# ---------------------------------------------------------------------------
# 2) Final tahmin sorusu zor havuzdan
# ---------------------------------------------------------------------------

class TestFinalEstimationHardPool:
    """Normal maçta 5. tur (tahmin) tercih sırası zor→kolay."""

    @pytest.mark.asyncio
    async def test_final_tahmin_prefers_hard_pool(self, db_session):
        """d2 ve d5 tahmin varken normal maç finali d5'i seçmeli; diğer turlar <=3."""
        from app.services.question_service import QuestionService

        db_session.add_all([
            _mk_q("q_cs1", QuestionType.COKTAN_SECMELI, 2),
            _mk_q("q_dy1", QuestionType.DOGRU_YANLIS, 2),
            _mk_q("q_go1", QuestionType.GORSEL, 2),
            _mk_q("q_ka1", QuestionType.KARSILASTIRMA, 2),
            _mk_q("q_ta_easy", QuestionType.TAHMIN, 2),
            _mk_q("q_ta_hard", QuestionType.TAHMIN, 5),
        ])
        await db_session.flush()

        qs = await QuestionService.get_questions_for_game(
            db_session, max_difficulty=3  # normal maç
        )

        assert len(qs) == 5
        # 5. tur: zor tahmin seçildi (kolay havuzda q_ta_easy dururken).
        assert qs[4].type == QuestionType.TAHMIN
        assert qs[4].id == "q_ta_hard"
        assert qs[4].difficulty >= 4
        # Diğer turların kolay→zor rampası değişmedi (hepsi <=3 havuzdan).
        assert all(q.difficulty <= 3 for q in qs[:4])

    @pytest.mark.asyncio
    async def test_final_tahmin_falls_back_to_easy_when_no_hard(self, db_session):
        """Zor tahmin yoksa gevşeme mevcut davranışa döner — maç sorusuz kalmaz."""
        from app.services.question_service import QuestionService

        db_session.add_all([
            _mk_q("q_cs1", QuestionType.COKTAN_SECMELI, 1),
            _mk_q("q_dy1", QuestionType.DOGRU_YANLIS, 1),
            _mk_q("q_go1", QuestionType.GORSEL, 2),
            _mk_q("q_ka1", QuestionType.KARSILASTIRMA, 2),
            _mk_q("q_ta_easy", QuestionType.TAHMIN, 2),  # tek tahmin: kolay
        ])
        await db_session.flush()

        qs = await QuestionService.get_questions_for_game(
            db_session, max_difficulty=3
        )

        assert len(qs) == 5
        assert qs[4].id == "q_ta_easy"  # zor yok → kolay tahmine düştü


# ---------------------------------------------------------------------------
# 3) Misafirler sıralamaya giremez
# ---------------------------------------------------------------------------

class TestGuestLeaderboardFilter:
    """is_guest=True kullanıcılar listelenmez; kendilerine guest_hidden döner."""

    @pytest.mark.asyncio
    async def test_guest_hidden_from_all_time(self, client):
        """All-time listesinde misafir yok; misafir sorgusunda guest_hidden=true."""
        from app.utils.security import create_access_token

        async with session_factory() as db:
            normal = await _mk_user(db, total_score=500)
            guest = await _mk_user(db, is_guest=True, total_score=900)
            await db.commit()
            normal_id, guest_id = str(normal.id), str(guest.id)
            normal_name = normal.username

        # Liste: misafir (daha yüksek skora rağmen) yok, normal 1. sırada.
        resp = await client.get("/api/leaderboard/all_time")
        assert resp.status_code == 200
        data = resp.json()
        ids = [e["user_id"] for e in data["entries"]]
        assert guest_id not in ids
        assert normal_id in ids
        assert data["entries"][0]["username"] == normal_name
        assert data["guest_hidden"] is False  # anonim istek

        # Misafirin kendi sorgusu: guest_hidden=true, my_entry yok.
        guest_token = create_access_token(guest_id)
        resp = await client.get(
            "/api/leaderboard/all_time",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        data = resp.json()
        assert data["guest_hidden"] is True
        assert data["my_entry"] is None

        # Normal kullanıcı: guest_hidden=false, my_entry rank 1 (misafir sayılmadı).
        normal_token = create_access_token(normal_id)
        resp = await client.get(
            "/api/leaderboard/all_time",
            headers={"Authorization": f"Bearer {normal_token}"},
        )
        data = resp.json()
        assert data["guest_hidden"] is False
        assert data["my_entry"]["rank"] == 1

    @pytest.mark.asyncio
    async def test_guest_hidden_from_season_and_settlement(self, client, db_session):
        """Sezon listesi + sezon sonu ödülleri misafiri dışlar; guest_hidden döner."""
        from app.services.tournament_service import TournamentService
        from app.utils.security import create_access_token
        from app.utils.season_util import season_id_for

        normal = await _mk_user(db_session, total_score=100)
        guest = await _mk_user(db_session, is_guest=True, total_score=100)
        sid = season_id_for()
        await TournamentService.add_season_points(db_session, str(normal.id), 300)
        await TournamentService.add_season_points(db_session, str(guest.id), 900)
        await db_session.commit()
        normal_id, guest_id = str(normal.id), str(guest.id)

        guest_token = create_access_token(guest_id)
        resp = await client.get(
            "/api/leaderboard/season",
            headers={"Authorization": f"Bearer {guest_token}"},
        )
        assert resp.status_code == 200
        data = resp.json()
        ids = [e["user_id"] for e in data["entries"]]
        assert guest_id not in ids       # misafir listede yok
        assert normal_id in ids
        assert data["entries"][0]["rank"] == 1  # rank görünen listeyle akar
        assert data["guest_hidden"] is True
        assert data["my_entry"] is None

        # Sezon sonu ödül hesabı: en yüksek puanlı MİSAFİR olsa bile ödül
        # görünen sıralamaya (misafirsiz) göre dağıtılır.
        settle = await TournamentService.settle_season(db_session, sid)
        winner_ids = [w["user_id"] for w in settle["winners"]]
        assert guest_id not in winner_ids
        assert normal_id in winner_ids
        assert settle["winners"][0]["rank"] == 1
