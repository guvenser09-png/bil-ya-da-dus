"""Tests for score calculation service."""

import pytest

from app.services.score_service import calculate_round_score, calculate_game_score


class TestCalculateRoundScore:
    """Test round score calculation."""

    def test_wrong_answer_returns_zero(self):
        """Wrong answers should earn 0 points."""
        assert calculate_round_score(5.0, is_correct=False, streak_count=0) == 0

    def test_correct_answer_base_points(self):
        """Correct answer with 0 time remaining should earn base 5 points."""
        score = calculate_round_score(0.0, is_correct=True, streak_count=0)
        assert score == 5

    def test_speed_bonus(self):
        """Faster answers should earn more points."""
        slow = calculate_round_score(1.0, is_correct=True, streak_count=0)
        fast = calculate_round_score(5.0, is_correct=True, streak_count=0)
        assert fast > slow

    def test_speed_bonus_calculation(self):
        """Speed bonus should be time_remaining * 2."""
        score = calculate_round_score(3.0, is_correct=True, streak_count=0)
        # 5 (base) + 6 (3.0 * 2) = 11
        assert score == 11

    def test_streak_multiplier_1(self):
        """1 streak should apply 1.2x multiplier."""
        no_streak = calculate_round_score(3.0, is_correct=True, streak_count=0)
        streak_1 = calculate_round_score(3.0, is_correct=True, streak_count=1)
        assert streak_1 > no_streak
        assert streak_1 == int(11 * 1.2)  # 13

    def test_streak_multiplier_2(self):
        """2 streak should apply 1.5x multiplier."""
        score = calculate_round_score(3.0, is_correct=True, streak_count=2)
        assert score == int(11 * 1.5)  # 16

    def test_streak_multiplier_3_plus(self):
        """3+ streak should apply 2x multiplier."""
        score = calculate_round_score(3.0, is_correct=True, streak_count=3)
        assert score == int(11 * 2.0)  # 22

    def test_streak_5_same_as_3(self):
        """5 streak should also apply 2x (max multiplier)."""
        s3 = calculate_round_score(3.0, is_correct=True, streak_count=3)
        s5 = calculate_round_score(3.0, is_correct=True, streak_count=5)
        assert s3 == s5


class TestCalculateGameScore:
    """Test total game score calculation."""

    def test_survival_base_score(self):
        """Base score = rounds survived × 10."""
        score = calculate_game_score(rounds_survived=3, round_scores=[], is_winner=False)
        assert score == 30

    def test_round_scores_added(self):
        """Round scores should be summed."""
        score = calculate_game_score(
            rounds_survived=2,
            round_scores=[10, 15],
            is_winner=False,
        )
        assert score == 20 + 10 + 15  # 45

    def test_victory_bonus(self):
        """Winner gets +100 bonus."""
        loser = calculate_game_score(rounds_survived=5, round_scores=[20], is_winner=False)
        winner = calculate_game_score(rounds_survived=5, round_scores=[20], is_winner=True)
        assert winner - loser == 100

    def test_full_game_winner_score(self):
        """A full game winner should score approximately 250-280."""
        # 5 rounds × 10 = 50 base
        # Round scores example: 15 + 13 + 16 + 22 + 11 = 77
        # Victory bonus: 100
        # Total: 227
        round_scores = [15, 13, 16, 22, 11]
        score = calculate_game_score(
            rounds_survived=5,
            round_scores=round_scores,
            is_winner=True,
        )
        assert 200 <= score <= 300

    def test_eliminated_round_2(self):
        """Player eliminated at round 2 should have limited score."""
        score = calculate_game_score(
            rounds_survived=2,
            round_scores=[10, 0],
            is_winner=False,
        )
        assert score == 30  # 2×10 + 10 + 0
