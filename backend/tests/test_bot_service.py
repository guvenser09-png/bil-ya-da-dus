"""Tests for bot service."""

import pytest

from app.services.bot_service import (
    generate_bot_name,
    generate_bot_answer_time,
    should_bot_answer_correctly,
)


class TestBotNameGeneration:
    """Test bot name generation."""

    def test_returns_string(self):
        """Bot name should be a non-empty string."""
        name = generate_bot_name()
        assert isinstance(name, str)
        assert len(name) > 0

    def test_names_are_varied(self):
        """Multiple calls should produce different names (not always)."""
        names = {generate_bot_name() for _ in range(20)}
        assert len(names) > 1  # At least 2 unique names out of 20


class TestBotAnswerCorrectness:
    """Test bot answer probability."""

    def test_easy_bot_roughly_50_percent(self):
        """Easy bots should answer correctly ~50% of the time."""
        results = [should_bot_answer_correctly("easy", 1) for _ in range(1000)]
        correct_rate = sum(results) / len(results)
        assert 0.35 < correct_rate < 0.65

    def test_hard_bot_roughly_85_percent(self):
        """Hard bots should answer correctly ~85% of the time."""
        results = [should_bot_answer_correctly("hard", 1) for _ in range(1000)]
        correct_rate = sum(results) / len(results)
        assert 0.70 < correct_rate < 0.95

    def test_later_rounds_slightly_harder(self):
        """Later rounds should reduce accuracy slightly."""
        r1 = sum(should_bot_answer_correctly("medium", 1) for _ in range(1000)) / 1000
        r5 = sum(should_bot_answer_correctly("medium", 5) for _ in range(1000)) / 1000
        assert r1 > r5  # Round 1 should be easier than round 5


class TestBotAnswerTime:
    """Test bot answer timing."""

    def test_within_range(self):
        """Answer time should be between 1 and 7 seconds."""
        for _ in range(100):
            time = generate_bot_answer_time()
            assert 1.0 <= time <= 7.0

    def test_varied_timing(self):
        """Times should not all be the same."""
        times = {generate_bot_answer_time() for _ in range(50)}
        assert len(times) > 5
