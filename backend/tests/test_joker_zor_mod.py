"""Zor Mod süre/kalkan + %50 JOKER testleri (Görev 5-6-7-8).

Kapsam:
  - GÖREV 7/8: Zor Mod 1-4. tur = 10 sn, tüm modlarda son tahmin turu = 12 sn.
  - GÖREV 5: turnuva (Zor Mod) maçında HİÇBİR oyuncu (gerçek/bot) kalkan almaz.
  - GÖREV 6: %50 JOKER — 4 şıklı çoktan-seçmeli soruda 2 YANLIŞ şıkkı eler;
    doğrulama (joker_precheck), gizli şık seçimi (doğru şık asla gizlenmez) ve
    WS handler'ın (_handle_use_joker) tam sözleşmesi (joker_result/joker_error,
    JOKER_COST kalıcı tahsilat, çift-tahsilat koruması).

NOT: Bu testler yalnızca YAZILDI; ortak test.db yarışını önlemek için burada
ÇALIŞTIRILMAZ (orkestratör merge sonrası tüm suite'i çalıştırır). Joker WS
handler testleri DB'yi monkeypatch ile taklit eder — gerçek DB'ye dokunmaz.
"""

import json

from app.services.game_service import (
    JOKER_COST,
    ROUND_CONFIG,
    TOURNAMENT_ROUND_CONFIG,
    GameEngine,
)
from app.ws.game import _handle_use_joker


# ---------------------------------------------------------------------------
# Yardımcılar
# ---------------------------------------------------------------------------

def _mk_engine(game_id: str = "g_joker", is_tournament: bool = False) -> GameEngine:
    players = [
        {"user_id": "u1", "username": "ayse", "display_name": "Ayşe", "avatar_id": "a"},
        {"user_id": "u2", "username": "veli", "display_name": "Veli", "avatar_id": "a"},
    ]
    bots = [{"bot_name": "bot1", "difficulty": "easy", "avatar_id": "a"}]
    return GameEngine(game_id, players, bots, is_tournament=is_tournament)


def _mc4_question(correct: int = 2) -> dict:
    """4 şıklı çoktan-seçmeli örnek soru (joker'e UYGUN)."""
    return {
        "id": "q1",
        "type": "coktan_secmeli",
        "question": "Hangisi?",
        "options": ["A", "B", "C", "D"],
        "correct_answer": correct,
    }


def _tf_question() -> dict:
    """Doğru/Yanlış (2 şık) — joker'e UYGUN DEĞİL."""
    return {
        "id": "q2",
        "type": "dogru_yanlis",
        "question": "Doğru mu?",
        "options": ["Doğru", "Yanlış"],
        "correct_answer": 0,
    }


def _tahmin_question() -> dict:
    """Tahmin (sayısal) — joker'e UYGUN DEĞİL."""
    return {
        "id": "q3",
        "type": "tahmin",
        "question": "Kaç milyon?",
        "options": None,
        "real_answer": 85,
        "min_value": 0,
        "max_value": 150,
    }


class _FakeUser:
    def __init__(self, coins: int):
        self.coins = coins


class _FakeSession:
    """`async with async_session_factory() as db:` taklidi."""

    def __init__(self):
        self.committed = False

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def commit(self):
        self.committed = True


class _FakeWS:
    """send_text ile gönderilen mesajları toplayan sahte WebSocket."""

    def __init__(self):
        self.sent: list[dict] = []

    async def send_text(self, data: str):
        self.sent.append(json.loads(data))


def _patch_db(monkeypatch, user: "_FakeUser | None"):
    """UserService.get_user_by_id + async_session_factory'yi taklit et."""
    async def _get(db, user_id):
        return user

    monkeypatch.setattr("app.ws.game.UserService.get_user_by_id", _get)
    monkeypatch.setattr("app.ws.game.async_session_factory", lambda: _FakeSession())


# ---------------------------------------------------------------------------
# GÖREV 7/8 — Tur süreleri
# ---------------------------------------------------------------------------

class TestRoundTimes:
    def test_final_estimation_is_12s_both_modes(self):
        # Son tahmin turu TÜM modlarda 12 sn.
        assert ROUND_CONFIG[4]["type"] == "tahmin"
        assert ROUND_CONFIG[4]["time"] == 12
        assert TOURNAMENT_ROUND_CONFIG[4]["type"] == "tahmin"
        assert TOURNAMENT_ROUND_CONFIG[4]["time"] == 12

    def test_tournament_first_four_rounds_are_10s(self):
        # Zor Mod 1-4. tur = 10 sn (yüksek risk).
        assert [c["time"] for c in TOURNAMENT_ROUND_CONFIG] == [10, 10, 10, 10, 12]

    def test_normal_first_four_times_unchanged(self):
        # Normal maç 1-4 süreleri DEĞİŞMEDİ (9/7/9/9); sadece final 12 oldu.
        assert [c["time"] for c in ROUND_CONFIG[:4]] == [9, 7, 9, 9]

    def test_round_config_time_feeds_client_and_server(self):
        # get_round_config turnuvada 10 sn döndürür (start_round + server timer
        # tek kaynak buradan beslenir).
        eng = _mk_engine(is_tournament=True)
        eng.current_round = 1
        assert eng.get_round_config()["time"] == 10
        eng.current_round = 5
        assert eng.get_round_config()["time"] == 12


# ---------------------------------------------------------------------------
# GÖREV 5 — Zor Mod'da kalkan YOK
# ---------------------------------------------------------------------------

class TestTournamentNoShields:
    async def test_tournament_zeroes_all_shields(self):
        eng = _mk_engine(is_tournament=True)
        # Constructor herkese 1 kalkan verir; setup turnuvada hepsini sıfırlar.
        for p in eng.players.values():
            assert p.shields == 1
        await eng.apply_shield_setup()  # turnuva dalı DB'ye dokunmaz
        for p in eng.players.values():
            assert p.shields == 0, f"{p.username} kalkanı sıfırlanmadı"
        assert eng._shield_setup_done is True

    async def test_tournament_setup_idempotent(self):
        eng = _mk_engine(is_tournament=True)
        await eng.apply_shield_setup()
        # İkinci çağrı sessizce geri döner (bayrak set).
        await eng.apply_shield_setup()
        for p in eng.players.values():
            assert p.shields == 0

    def test_normal_match_bots_keep_shield(self):
        # Normal maçta davranış değişmez: botlar constructor kalkanında (1) kalır.
        eng = _mk_engine(is_tournament=False)
        for p in eng.players.values():
            if p.is_bot:
                assert p.shields == 1


# ---------------------------------------------------------------------------
# GÖREV 6 — %50 JOKER: engine doğrulama + gizli şık seçimi
# ---------------------------------------------------------------------------

class TestJokerEngineLogic:
    def test_cost_constant_is_50(self):
        assert JOKER_COST == 50

    def test_player_default_joker_unused(self):
        eng = _mk_engine()
        assert eng.players["ayse"].joker_used is False

    def test_precheck_ok_on_4option_mc(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        ok, reason = eng.joker_precheck("ayse", 1)
        assert ok is True
        assert reason == ""

    def test_precheck_not_eligible_true_false(self):
        eng = _mk_engine()
        eng.start_round(_tf_question())
        assert eng.joker_precheck("ayse", 1) == (False, "not_eligible")

    def test_precheck_not_eligible_tahmin(self):
        eng = _mk_engine()
        eng.start_round(_tahmin_question())
        assert eng.joker_precheck("ayse", 1) == (False, "not_eligible")

    def test_precheck_too_late_after_answer(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.submit_answer("ayse", 0, 3.0)
        assert eng.joker_precheck("ayse", 1) == (False, "too_late")

    def test_precheck_too_late_round_not_active(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.status = "round_end"
        assert eng.joker_precheck("ayse", 1) == (False, "too_late")

    def test_precheck_too_late_stale_round_number(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        # İstemci bayat/yanlış tur numarası bildirirse reddedilir.
        assert eng.joker_precheck("ayse", 99) == (False, "too_late")

    def test_precheck_too_late_for_eliminated(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.players["ayse"].is_alive = False
        assert eng.joker_precheck("ayse", 1) == (False, "too_late")

    def test_precheck_already_used(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.players["ayse"].joker_used = True
        assert eng.joker_precheck("ayse", 1) == (False, "already_used")

    def test_hidden_hides_two_wrong_keeps_correct(self):
        eng = _mk_engine()
        eng.start_round(_mc4_question(correct=2))
        hidden = eng.compute_joker_hidden_options()
        assert hidden is not None
        assert len(hidden) == 2
        assert 2 not in hidden  # doğru şık ASLA gizlenmez
        assert all(i in (0, 1, 3) for i in hidden)  # gizlenenler yanlış şıklar
        visible = [i for i in range(4) if i not in hidden]
        assert visible.count(2) == 1  # doğru şık görünür
        assert len(visible) == 2      # doğru + 1 yanlış görünür kalır

    def test_hidden_never_hides_correct_any_index(self):
        # Doğru şık hangi indekste olursa olsun (0-3) hiçbir zaman gizlenmez.
        for correct in range(4):
            eng = _mk_engine()
            eng.start_round(_mc4_question(correct=correct))
            for _ in range(25):
                hidden = eng.compute_joker_hidden_options()
                assert hidden is not None
                assert correct not in hidden
                assert len(hidden) == 2

    def test_hidden_none_for_non_mc(self):
        eng = _mk_engine()
        eng.start_round(_tf_question())
        assert eng.compute_joker_hidden_options() is None

    def test_joker_available_in_tournament(self):
        # Joker Zor Mod dahil tüm maç tiplerinde kullanılabilir.
        eng = _mk_engine(is_tournament=True)
        eng.start_round(_mc4_question())
        ok, reason = eng.joker_precheck("ayse", 1)
        assert ok is True


# ---------------------------------------------------------------------------
# GÖREV 6 — %50 JOKER: WS handler tam sözleşmesi (_handle_use_joker)
# ---------------------------------------------------------------------------

class TestJokerWsHandler:
    async def test_success_deducts_and_sends_result(self, monkeypatch):
        eng = _mk_engine()
        eng.start_round(_mc4_question(correct=2))
        user = _FakeUser(coins=100)
        _patch_db(monkeypatch, user)
        ws = _FakeWS()

        await _handle_use_joker(
            eng, "u1", {"type": "use_joker", "round_number": 1}, ws
        )

        # Coin kalıcı düşüldü, joker kullanıldı işaretlendi.
        assert user.coins == 100 - JOKER_COST
        assert eng.players["ayse"].joker_used is True
        # Tek kişisel joker_result mesajı, sözleşme şeklinde.
        assert len(ws.sent) == 1
        msg = ws.sent[0]
        assert msg["type"] == "joker_result"
        assert msg["round_number"] == 1
        assert msg["coins"] == 50
        assert len(msg["hidden_options"]) == 2
        assert 2 not in msg["hidden_options"]

    async def test_insufficient_does_not_charge(self, monkeypatch):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        user = _FakeUser(coins=JOKER_COST - 1)
        _patch_db(monkeypatch, user)
        ws = _FakeWS()

        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws)

        assert user.coins == JOKER_COST - 1  # düşülmedi
        assert eng.players["ayse"].joker_used is False
        assert ws.sent == [{"type": "joker_error", "reason": "insufficient"}]

    async def test_already_used_rejected_before_db(self, monkeypatch):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.players["ayse"].joker_used = True
        # DB'ye ULAŞILMAMALI — patch'lersek çağrılırsa yakalanır.
        user = _FakeUser(coins=1000)
        _patch_db(monkeypatch, user)
        ws = _FakeWS()

        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws)

        assert user.coins == 1000  # tahsilat yok
        assert ws.sent == [{"type": "joker_error", "reason": "already_used"}]

    async def test_not_eligible_true_false(self, monkeypatch):
        eng = _mk_engine()
        eng.start_round(_tf_question())
        user = _FakeUser(coins=1000)
        _patch_db(monkeypatch, user)
        ws = _FakeWS()

        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws)

        assert user.coins == 1000
        assert ws.sent == [{"type": "joker_error", "reason": "not_eligible"}]

    async def test_too_late_after_answer(self, monkeypatch):
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        eng.submit_answer("ayse", 0, 3.0)
        user = _FakeUser(coins=1000)
        _patch_db(monkeypatch, user)
        ws = _FakeWS()

        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws)

        assert user.coins == 1000
        assert ws.sent == [{"type": "joker_error", "reason": "too_late"}]

    async def test_double_use_second_is_already_used(self, monkeypatch):
        # İlk kullanım başarılı; ikinci kullanım (aynı maç) already_used.
        eng = _mk_engine()
        eng.start_round(_mc4_question())
        user = _FakeUser(coins=200)
        _patch_db(monkeypatch, user)

        ws1 = _FakeWS()
        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws1)
        assert ws1.sent[0]["type"] == "joker_result"
        assert user.coins == 150

        ws2 = _FakeWS()
        await _handle_use_joker(eng, "u1", {"round_number": 1}, ws2)
        assert ws2.sent == [{"type": "joker_error", "reason": "already_used"}]
        assert user.coins == 150  # ikinci kez tahsilat YOK (çift-tahsilat koruması)
