"""Tests for game engine."""

import pytest

from app.services.game_service import (
    ROUND_CONFIG,
    TOURNAMENT_ROUND_CONFIG,
    GameEngine,
)


def _create_test_engine() -> GameEngine:
    """Create a game engine with 3 real players and 2 bots."""
    players = [
        {"user_id": "u1", "username": "player1", "display_name": "Player 1", "avatar_id": "default_01"},
        {"user_id": "u2", "username": "player2", "display_name": "Player 2", "avatar_id": "default_02"},
        {"user_id": "u3", "username": "player3", "display_name": "Player 3", "avatar_id": "default_03"},
    ]
    bots = [
        {"bot_name": "bot1", "difficulty": "easy", "avatar_id": "default_04"},
        {"bot_name": "bot2", "difficulty": "hard", "avatar_id": "default_05"},
    ]
    return GameEngine("test-game-1", players, bots)


class TestGameEngineInit:
    """Test game engine initialization."""

    def test_initial_state(self):
        engine = _create_test_engine()
        assert engine.status == "waiting"
        assert engine.current_round == 0
        assert len(engine.players) == 5  # 3 real + 2 bots
        assert engine.alive_count == 5

    def test_alive_players(self):
        engine = _create_test_engine()
        assert len(engine.alive_real_players) == 3

    def test_round_config(self):
        # Eleme rampası: ilk tur kolay 4 şıklı ısınma, final tahmin.
        assert ROUND_CONFIG[0]["type"] == "coktan_secmeli"
        assert ROUND_CONFIG[1]["type"] == "dogru_yanlis"
        assert ROUND_CONFIG[2]["type"] == "gorsel"
        assert ROUND_CONFIG[3]["type"] == "karsilastirma"
        assert ROUND_CONFIG[4]["type"] == "tahmin"
        assert len(ROUND_CONFIG) == 5
        # Zorluk merdiveni 1-5 sıralı.
        assert [c["difficulty"] for c in ROUND_CONFIG] == [1, 2, 3, 4, 5]
        # Turnuva config'i aynı TİP sırasında (cömert sürelerle).
        assert [c["type"] for c in TOURNAMENT_ROUND_CONFIG] == [
            c["type"] for c in ROUND_CONFIG
        ]
        assert [c["difficulty"] for c in TOURNAMENT_ROUND_CONFIG] == [1, 2, 3, 4, 5]

    def test_players_start_with_one_shield(self):
        """Herkes (botlar DAHİL) maça 1 Kalkanla başlar."""
        engine = _create_test_engine()
        for p in engine.players.values():
            assert p.shields == 1


class TestRoundManagement:
    """Test round start, answer submission, and resolution."""

    def test_start_round(self):
        engine = _create_test_engine()
        question = {"content": "Test question?", "options": ["A", "B"], "id": "q_001"}
        result = engine.start_round(question)

        assert result["type"] == "round_start"
        assert result["round"] == 1
        assert engine.status == "round_active"
        assert engine.current_round == 1

    def test_submit_answer(self):
        engine = _create_test_engine()
        engine.start_round({"content": "Q?", "options": ["A", "B"]})

        success = engine.submit_answer("player1", 0, 3.5)
        assert success is True

    def test_submit_answer_dead_player(self):
        engine = _create_test_engine()
        engine.start_round({"content": "Q?", "options": ["A", "B"]})
        engine.players["player1"].is_alive = False

        success = engine.submit_answer("player1", 0, 3.5)
        assert success is False

    def test_submit_duplicate_answer(self):
        engine = _create_test_engine()
        engine.start_round({"content": "Q?", "options": ["A", "B"]})
        engine.submit_answer("player1", 0, 3.5)

        success = engine.submit_answer("player1", 1, 2.0)
        assert success is False  # Already answered

    def test_end_round_correct_survive(self):
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        # All answer correctly
        for p in engine.alive_players:
            p.current_answer = 0
            p.answer_time = 3.0

        result = engine.end_round(correct_answer=0, question=question)
        assert len(result.eliminated) == 0
        assert len(result.survivors) == 5

    def test_end_round_wrong_eliminated(self):
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        # Kalkanı tükenmiş player1 yanlış cevaplar → normal eleme.
        engine.players["player1"].shields = 0
        engine.players["player1"].current_answer = 1
        engine.players["player1"].answer_time = 3.0
        for p in engine.alive_players:
            if p.username != "player1":
                p.current_answer = 0
                p.answer_time = 3.0

        result = engine.end_round(correct_answer=0, question=question)
        assert "player1" in result.eliminated
        assert engine.players["player1"].is_alive is False

    def test_reversed_options_index_scored_by_position(self):
        """Ters sıralı dogru_yanlis: ekrandaki doğru şıkkın İNDEKSİ doğru sayılır.

        Regresyon: mobil TrueFalseWidget eskiden 'DOĞRU' etiketini SABİT index 0
        kabul ediyordu. options ['Yanlış','Doğru'] (correct_answer=1) gelince,
        ekranda 'Doğru'ya basan oyuncunun gönderdiği index 0 olup YANLIŞ
        sayılıyor ve eleniyordu. Doğru davranış: oyuncu ekrandaki gerçek indeksi
        (1) gönderir → doğru sayılır/hayatta; sabit 0 gönderen → yanlış/elenir.
        """
        engine = _create_test_engine()
        # options TERS sırada; doğru şık 'Doğru' index 1'de.
        question = {
            "content": "Q?",
            "type": "dogru_yanlis",
            "options": ["Yanlış", "Doğru"],
        }
        engine.start_round(question)

        # player1: ekrandaki doğru şıkkı (index 1) seçer → doğru/hayatta.
        engine.players["player1"].current_answer = 1
        engine.players["player1"].answer_time = 3.0
        # player2: eski sabit-eşleme gibi index 0 gönderir → yanlış/elenir.
        # (Kalkanı sıfırlanır ki kalkan kurtarması elemeyi maskelemesin.)
        engine.players["player2"].shields = 0
        engine.players["player2"].current_answer = 0
        engine.players["player2"].answer_time = 3.0
        # Kalanlar da doğru (index 1) ki "herkes yanlış → kimse elenmez" kuralı
        # devreye girmesin ve player2 gerçekten elensin.
        for p in engine.alive_players:
            if p.username not in ("player1", "player2"):
                p.current_answer = 1
                p.answer_time = 3.0

        result = engine.end_round(correct_answer=1, question=question)

        assert result.player_answers["player1"]["correct"] is True
        assert "player1" in result.survivors
        assert engine.players["player1"].is_alive is True
        assert result.player_answers["player2"]["correct"] is False
        assert "player2" in result.eliminated

    def test_all_wrong_no_elimination(self):
        """If everyone answers wrong, nobody is eliminated.

        KALKAN ETKİLEŞİMİ: bu kural kalkandan ÖNCE uygulanır — kimse
        elenmeyeceği için kimsenin kalkanı da KIRILMAZ.
        """
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        for p in engine.alive_players:
            p.current_answer = 1  # All wrong
            p.answer_time = 3.0

        result = engine.end_round(correct_answer=0, question=question)
        assert len(result.eliminated) == 0  # Nobody eliminated
        assert engine.alive_count == 5
        # Kalkanlar boşa harcanmadı, kimse "kalkanla kurtuldu" sayılmadı.
        assert result.shield_saved == []
        for p in engine.players.values():
            assert p.shields == 1


class TestShieldMechanic:
    """Kalkan (🛡️) mekaniği testleri."""

    def test_shield_saves_first_wrong(self):
        """İlk yanlışta kalkan KIRILIR, oyuncu hayatta kalır ama puan almaz."""
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        engine.players["player1"].current_answer = 1  # yanlış
        engine.players["player1"].answer_time = 3.0
        for p in engine.alive_players:
            if p.username != "player1":
                p.current_answer = 0
                p.answer_time = 3.0

        result = engine.end_round(correct_answer=0, question=question)

        # Elenmedi, kalkanıyla kurtuldu.
        assert "player1" not in result.eliminated
        assert "player1" in result.survivors
        assert result.shield_saved == ["player1"]
        assert engine.players["player1"].is_alive is True
        assert engine.players["player1"].shields == 0
        # Yanlış cevapladı: puan YOK, correct=False, streak sıfır.
        assert result.player_answers["player1"]["correct"] is False
        assert result.player_answers["player1"]["score"] == 0
        assert engine.players["player1"].streak == 0
        # Reveal payload'ı sözleşmeye uygun: shield_saved listesi mesajda var.
        msg = engine.get_round_end_message(result)
        assert msg["shield_saved"] == ["player1"]
        assert msg["results"]["player1"]["shield_saved"] is True
        # Doğru cevaplayanların kalkanı yerinde duruyor.
        assert engine.players["player2"].shields == 1

    def test_second_wrong_eliminates(self):
        """Kalkan tek kullanımlık: ikinci yanlış = normal eleme."""
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}

        # Tur 1: player1 yanlış → kalkan kırılır, hayatta.
        engine.start_round(question)
        engine.players["player1"].current_answer = 1
        engine.players["player1"].answer_time = 3.0
        for p in engine.alive_players:
            if p.username != "player1":
                p.current_answer = 0
                p.answer_time = 3.0
        engine.end_round(correct_answer=0, question=question)
        assert engine.players["player1"].is_alive is True
        assert engine.players["player1"].shields == 0

        # Tur 2: player1 yine yanlış → kalkan yok, elenir.
        engine.start_round(question)
        engine.players["player1"].current_answer = 1
        engine.players["player1"].answer_time = 3.0
        for p in engine.alive_players:
            if p.username != "player1":
                p.current_answer = 0
                p.answer_time = 3.0
        result = engine.end_round(correct_answer=0, question=question)

        assert "player1" in result.eliminated
        assert result.shield_saved == []
        assert engine.players["player1"].is_alive is False
        assert engine.players["player1"].eliminated_at_round == 2

    def test_shield_invalid_in_final_round(self):
        """Final (tahmin) turunda kalkan GEÇERSİZ: uzak tahmin kalkana rağmen elenir."""
        engine = _create_test_engine()
        engine.current_round = 4  # start_round → 5. tur (tahmin)
        question = {
            "content": "Tahmin?",
            "min_value": 0,
            "max_value": 1000,
            "real_answer": 500,
        }
        engine.start_round(question)

        # player1 kalkanlı ama tolerans bandının (±100) çok dışında.
        assert engine.players["player1"].shields == 1
        engine.players["player1"].current_answer = 990
        engine.players["player1"].answer_time = 3.0
        for p in engine.alive_players:
            if p.username != "player1":
                p.current_answer = 505
                p.answer_time = 3.0

        result = engine.end_round(correct_answer=500, question=question)

        # Kalkan finali kurtarmaz: player1 elendi, kalkanı da harcanmadı.
        assert "player1" in result.eliminated
        assert engine.players["player1"].is_alive is False
        assert result.shield_saved == []
        assert engine.players["player1"].shields == 1

    def test_round_start_payload_includes_shields(self):
        """round_start ve game_state oyuncu listelerinde shields alanı bulunur."""
        engine = _create_test_engine()
        msg = engine.start_round({"content": "Q?", "options": ["A", "B"]})
        for entry in msg["players"]:
            assert entry["shields"] == 1
        for entry in engine.players_summary():
            assert entry["shields"] == 1


class TestGhostMode:
    """Hayalet modu (👻) testleri — elenen oyuncu gölge cevap verir."""

    def _eliminate(self, engine: GameEngine, username: str, at_round: int = 1):
        p = engine.players[username]
        p.is_alive = False
        p.eliminated_at_round = at_round
        p.shields = 0

    def test_ghost_answer_counted_without_affecting_results(self):
        """Doğru hayalet cevap sayaç artırır; eleme/skor/results'a karışmaz."""
        engine = _create_test_engine()
        self._eliminate(engine, "player1")
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        # Elenmiş player1 hayalet cevap verir (doğru).
        assert engine.submit_ghost_answer("player1", 0, 3.0) is True
        # Aynı turda ikinci hayalet cevap reddedilir.
        assert engine.submit_ghost_answer("player1", 1, 2.0) is False

        for p in engine.alive_players:
            p.current_answer = 0
            p.answer_time = 3.0
        result = engine.end_round(correct_answer=0, question=question)

        assert engine.players["player1"].ghost_correct == 1
        # Hayalet skoru/puanı YOK; results map'ine karışmadı.
        assert engine.players["player1"].score == 0
        assert "player1" not in result.player_answers
        assert "player1" not in result.survivors
        assert "player1" not in result.eliminated
        # Reveal payload'ında kişiye özel ghost_results girdisi var.
        msg = engine.get_round_end_message(result)
        assert msg["ghost_results"]["player1"]["correct"] is True
        assert "player1" not in msg["results"]

    def test_ghost_wrong_not_counted_and_alive_rejected(self):
        """Yanlış hayalet cevap sayaç artırmaz; HAYATTA olan hayalet olamaz."""
        engine = _create_test_engine()
        self._eliminate(engine, "player1")
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        # Hayatta olan player2'nin hayalet cevabı reddedilir.
        assert engine.submit_ghost_answer("player2", 0, 3.0) is False
        # player1 yanlış hayalet cevap verir.
        assert engine.submit_ghost_answer("player1", 1, 3.0) is True

        for p in engine.alive_players:
            p.current_answer = 0
            p.answer_time = 3.0
        result = engine.end_round(correct_answer=0, question=question)

        assert engine.players["player1"].ghost_correct == 0
        assert result.ghost_results["player1"]["correct"] is False

    def test_ghost_estimation_tolerance(self):
        """Tahmin turunda tolerans bandı içindeki hayalet tahmin doğru sayılır."""
        engine = _create_test_engine()
        self._eliminate(engine, "player1", at_round=3)
        engine.current_round = 4  # start_round → 5. tur (tahmin)
        question = {
            "content": "Tahmin?",
            "min_value": 0,
            "max_value": 1000,
            "real_answer": 500,
        }
        engine.start_round(question)

        # Tolerans ±100: 560 içeride → doğru sayılmalı.
        assert engine.submit_ghost_answer("player1", 560, 3.0) is True
        for p in engine.alive_players:
            p.current_answer = 505
            p.answer_time = 3.0
        result = engine.end_round(correct_answer=500, question=question)

        assert engine.players["player1"].ghost_correct == 1
        assert result.ghost_results["player1"]["correct"] is True


class TestChampionBet:
    """Şampiyon bahsi (🎯) testleri."""

    def test_place_bet_valid_and_locked(self):
        """Elenmiş oyuncu hayatta kalana bahis koyar; ikinci bahis reddedilir."""
        engine = _create_test_engine()
        engine.players["player1"].is_alive = False
        engine.players["player1"].eliminated_at_round = 2

        ok, err = engine.place_champion_bet("player1", "player2")
        assert ok is True and err == ""
        assert engine.players["player1"].champion_bet == "player2"

        # Değiştirilemez: ikinci bahis reddedilir, ilk bahis korunur.
        ok, err = engine.place_champion_bet("player1", "player3")
        assert ok is False and err
        assert engine.players["player1"].champion_bet == "player2"

    def test_place_bet_invalid_cases(self):
        """Hayattayken, ölü hedefe veya olmayan oyuncuya bahis reddedilir."""
        engine = _create_test_engine()

        # Hayatta olan oyuncu bahis yapamaz.
        ok, _ = engine.place_champion_bet("player1", "player2")
        assert ok is False

        # Elenmiş oyuncu, ELENMİŞ bir hedefe bahis yapamaz.
        engine.players["player1"].is_alive = False
        engine.players["player2"].is_alive = False
        ok, _ = engine.place_champion_bet("player1", "player2")
        assert ok is False
        # Olmayan oyuncuya da yapamaz.
        ok, _ = engine.place_champion_bet("player1", "yok_boyle_biri")
        assert ok is False
        assert engine.players["player1"].champion_bet is None


class TestGhostAndBetRewards:
    """Hayalet altını + bahis ödülü hesap kuralları."""

    def test_ghost_reward_capped(self):
        from app.services.match_reward_service import (
            GHOST_GOLD_MAX,
            ghost_reward_for,
        )

        assert ghost_reward_for(0) == 0
        assert ghost_reward_for(1) == 5
        assert ghost_reward_for(4) == 20
        # Üst sınır: 4'ten fazla doğru bile olsa 20'yi aşamaz.
        assert ghost_reward_for(9) == GHOST_GOLD_MAX

    def test_bonus_coins_for_ghost_and_winning_bet(self):
        from app.ws.game import _bonus_coins_for

        engine = _create_test_engine()
        p = engine.players["player1"]
        p.is_alive = False
        p.ghost_correct = 3
        p.champion_bet = "player2"

        # Bahis tuttu: 3×5 hayalet + 25 bahis = 40.
        assert _bonus_coins_for(p, "player2") == 40
        # Bahis tutmadı: sadece hayalet altını.
        assert _bonus_coins_for(p, "player3") == 15
        # Kazanan belirsizse bahis ödenmez.
        assert _bonus_coins_for(p, None) == 15


class TestBotSimulation:
    """Test bot answer simulation."""

    def test_simulate_bot_answers(self):
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        engine.simulate_bot_answers(correct_answer=0, question=question)

        # Only bots should have answers
        assert engine.players["bot1"].current_answer is not None
        assert engine.players["bot2"].current_answer is not None
        assert engine.players["player1"].current_answer is None

    def test_simulate_estimation_bots(self):
        engine = _create_test_engine()
        engine.current_round = 4  # Set to round before final
        question = {
            "content": "Tahmin sorusu",
            "min_value": 0,
            "max_value": 1000,
            "real_answer": 500,
        }
        engine.start_round(question)  # This sets current_round to 5

        engine.simulate_bot_answers(correct_answer=500, question=question)

        for bot_name in ["bot1", "bot2"]:
            answer = engine.players[bot_name].current_answer
            assert answer is not None
            assert 0 <= answer <= 1000


class TestEstimationRound:
    """Test the final estimation round."""

    def test_closest_is_winner(self):
        """En yakın oyuncu "winner" bonusunu alır (tolerans=100, hepsi içinde)."""
        engine = _create_test_engine()
        # Skip to round 5
        engine.current_round = 4
        question = {
            "content": "Tahmin?",
            "min_value": 0,
            "max_value": 1000,
            "real_answer": 500,
        }
        engine.start_round(question)

        # Player1 guesses closest
        engine.players["player1"].current_answer = 505
        engine.players["player1"].answer_time = 4.0
        engine.players["player2"].current_answer = 400
        engine.players["player2"].answer_time = 3.0
        engine.players["player3"].current_answer = 600
        engine.players["player3"].answer_time = 3.0
        engine.players["bot1"].current_answer = 450
        engine.players["bot1"].answer_time = 3.0
        engine.players["bot2"].current_answer = 550
        engine.players["bot2"].answer_time = 3.0

        result = engine.end_round(correct_answer=500, question=question)
        # En yakın player1 winner olmalı.
        assert result.player_answers["player1"]["winner"] is True
        # Tolerans (±100) içindeki herkes hayatta kalır — doğru bilen elenmez.
        assert set(result.survivors) == {
            "player1", "player2", "player3", "bot1", "bot2"
        }

    def test_correct_guess_not_eliminated(self):
        """BUG FIX: doğru cevabı TAM tutturan oyuncu, bir rakip aynı/daha hızlı
        olsa bile ELENMEZ (eski winner-takes-all bug'ı)."""
        engine = _create_test_engine()
        engine.current_round = 4
        question = {
            "content": "Tahmin?",
            "min_value": 100,
            "max_value": 5000,
            "real_answer": 1506,
        }
        engine.start_round(question)

        # Player1 TAM doğru; bot aynı değeri daha hızlı verdi (eski tie-break'i
        # bot kazanır, player1 elenirdi).
        engine.players["player1"].current_answer = 1506
        engine.players["player1"].answer_time = 2.0
        engine.players["bot1"].current_answer = 1506
        engine.players["bot1"].answer_time = 5.0
        # Diğerleri çok uzak → elenmeli (battle royale daralması korunur).
        for u in ("player2", "player3", "bot2"):
            engine.players[u].current_answer = 4900
            engine.players[u].answer_time = 1.0

        result = engine.end_round(correct_answer=1506, question=question)
        assert "player1" in result.survivors
        assert engine.players["player1"].is_alive is True
        assert result.player_answers["player1"]["correct"] is True
        # Uzak tahminler elendi.
        assert "player2" in result.eliminated


class TestGameFinish:
    """Test game completion."""

    def test_finish_game(self):
        engine = _create_test_engine()
        engine.current_round = 5
        engine.players["player1"].is_alive = True
        engine.players["player1"].round_scores = [10, 12, 15, 8, 5]
        engine.players["player2"].is_alive = False
        engine.players["player2"].eliminated_at_round = 3
        engine.players["player2"].round_scores = [10, 12, 0]
        engine.players["player3"].is_alive = False
        engine.players["player3"].eliminated_at_round = 2
        engine.players["player3"].round_scores = [10, 0]
        engine.players["bot1"].is_alive = False
        engine.players["bot1"].eliminated_at_round = 1
        engine.players["bot1"].round_scores = [0]
        engine.players["bot2"].is_alive = False
        engine.players["bot2"].eliminated_at_round = 4
        engine.players["bot2"].round_scores = [10, 12, 15, 0]

        result = engine.finish_game()
        assert result["type"] == "game_over"
        assert result["winner"]["username"] == "player1"
        assert len(result["leaderboard"]) == 5
        assert result["leaderboard"][0]["score"] > result["leaderboard"][-1]["score"]
        assert engine.status == "finished"

    def test_game_over_message_format(self):
        engine = _create_test_engine()
        engine.current_round = 5
        engine.players["player1"].is_alive = True
        engine.players["player1"].round_scores = [5]

        result = engine.finish_game()
        assert "winner" in result
        assert "leaderboard" in result
        assert "duration_seconds" in result


class TestRoundRevealPayloadInvariants:
    """Reveal payload'ının 'bilen çok ama puan alan az' algısına karşı
    değişmezleri (invariant) — regresyon kilidi.

    Kullanıcı gözlemi araştırması sonucu: skorlama tutarlı; bu test o
    tutarlılığı kalıcı kılar:
      * results'ta correct=True olan HERKESİN (bot dahil) score'u > 0,
      * yanlış / kalkanla kurtulan / cevapsız oyuncunun score'u 0,
      * results.score = TUR puanı (total_score'dan ayrı alan),
      * hayalet (ghost) cevaplar results map'ine ASLA karışmaz.
    """

    def _twelve_player_engine(self) -> GameEngine:
        players = [
            {"user_id": "u1", "username": "gercek", "display_name": "Gerçek",
             "avatar_id": "default_01"},
        ]
        bots = [
            {"bot_name": f"bot{i}", "difficulty": "medium",
             "avatar_id": "default_02"}
            for i in range(11)
        ]
        return GameEngine("test-reveal-12p", players, bots)

    def test_correct_players_always_have_positive_round_score(self):
        engine = self._twelve_player_engine()
        question = {"content": "Q?", "options": ["A", "B", "C", "D"],
                    "type": "coktan_secmeli"}
        engine.start_round(question)

        # 8 doğru (bot dahil, farklı kalan sürelerle), 3 yanlış, 1 cevapsız.
        names = list(engine.players)
        for i, name in enumerate(names[:8]):
            engine.submit_answer(name, 1, 8.0 - i * 0.7)
        for name in names[8:11]:
            engine.submit_answer(name, 0, 3.0)
        # names[11] hiç cevap vermedi → yanlış sayılır.

        result = engine.end_round(correct_answer=1, question=question)
        msg = engine.get_round_end_message(result)
        results = msg["results"]

        # 12 oyuncunun TAMAMI results'ta (görünürlük kaybı yok).
        assert len(results) == 12

        # Doğru bilen HERKES (bot dahil) puan aldı; yanlışların puanı 0.
        for name, entry in results.items():
            if entry["correct"]:
                assert entry["score"] > 0, f"{name} doğru bildi ama puan 0"
            else:
                assert entry["score"] == 0, f"{name} yanlış ama puan almış"

        # "Bilen sayısı" == "puan alan sayısı" — algılanan tutarsızlık YOK.
        n_correct = sum(1 for e in results.values() if e["correct"])
        n_scored = sum(1 for e in results.values() if e["score"] > 0)
        assert n_correct == 8
        assert n_correct == n_scored

    def test_score_field_is_round_score_not_total(self):
        engine = self._twelve_player_engine()
        # Tur 2'ye önceden birikmiş puan koy → score alanı TUR puanı mı,
        # TOPLAM mı ayrışsın.
        engine.players["gercek"].score = 100
        question = {"content": "Q?", "options": ["A", "B"],
                    "type": "dogru_yanlis"}
        engine.start_round(question)
        for name in engine.players:
            engine.submit_answer(name, 0, 4.0)

        result = engine.end_round(correct_answer=0, question=question)
        msg = engine.get_round_end_message(result)
        entry = msg["results"]["gercek"]

        # score = SADECE bu turun puanı; total_score = birikmiş toplam.
        assert 0 < entry["score"] < 100
        assert entry["total_score"] == 100 + entry["score"]

    def test_shield_saved_players_get_zero_score_but_survive(self):
        engine = self._twelve_player_engine()
        question = {"content": "Q?", "options": ["A", "B", "C", "D"],
                    "type": "coktan_secmeli"}
        engine.start_round(question)

        names = list(engine.players)
        for name in names[:6]:
            engine.submit_answer(name, 2, 5.0)
        for name in names[6:]:
            engine.submit_answer(name, 0, 5.0)

        result = engine.end_round(correct_answer=2, question=question)
        msg = engine.get_round_end_message(result)

        # Yanlışlar kalkanla kurtuldu: hayatta ama correct=False ve score=0.
        for name in names[6:]:
            entry = msg["results"][name]
            assert entry["shield_saved"] is True
            assert entry["correct"] is False
            assert entry["score"] == 0
        # Kalkanla kurtulan "bilen" DEĞİLDİR → alive_count (12) doğru bilen
        # sayısından (6) fazla olabilir; bu bir skor hatası değildir.
        assert msg["alive_count"] == 12
        assert sum(1 for e in msg["results"].values() if e["correct"]) == 6

    def test_ghost_answers_never_leak_into_results(self):
        engine = self._twelve_player_engine()
        # gercek oyuncu elenmiş olsun → hayalet cevap verebilsin.
        engine.players["gercek"].is_alive = False
        engine.players["gercek"].eliminated_at_round = 1

        question = {"content": "Q?", "options": ["A", "B"],
                    "type": "dogru_yanlis"}
        engine.start_round(question)
        assert engine.submit_ghost_answer("gercek", 0, 3.0) is True
        for name in engine.players:
            if name != "gercek":
                engine.submit_answer(name, 0, 4.0)

        result = engine.end_round(correct_answer=0, question=question)
        msg = engine.get_round_end_message(result)

        # Hayalet, results map'inde YOK (bilen sayacını şişirmez)…
        assert "gercek" not in msg["results"]
        # …ama ghost_results'ta doğru işaretli; skoru DEĞİŞMEZ.
        assert msg["ghost_results"]["gercek"]["correct"] is True
        assert engine.players["gercek"].score == 0
