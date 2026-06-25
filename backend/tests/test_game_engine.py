"""Tests for game engine."""

import pytest

from app.services.game_service import GameEngine, ROUND_CONFIG


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
        assert ROUND_CONFIG[0]["type"] == "dogru_yanlis"
        assert ROUND_CONFIG[4]["type"] == "tahmin"
        assert len(ROUND_CONFIG) == 5


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

        # Player1 answers wrong, rest correct
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
        """If everyone answers wrong, nobody is eliminated."""
        engine = _create_test_engine()
        question = {"content": "Q?", "options": ["Doğru", "Yanlış"]}
        engine.start_round(question)

        for p in engine.alive_players:
            p.current_answer = 1  # All wrong
            p.answer_time = 3.0

        result = engine.end_round(correct_answer=0, question=question)
        assert len(result.eliminated) == 0  # Nobody eliminated
        assert engine.alive_count == 5


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
