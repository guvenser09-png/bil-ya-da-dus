"""Tests for app/services/anti_tilt_service.py — 6 scenarios."""

import json
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock(stored_value: str | None = None) -> AsyncMock:
    """Create an AsyncMock that behaves like a minimal Redis client."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=stored_value)
    mock.set = AsyncMock()
    mock.exists = AsyncMock(return_value=1 if stored_value else 0)
    return mock


def _results_json(results: list[dict]) -> str:
    return json.dumps(results)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_record_single_win():
    """Recording a single win stores exactly one result with won=True."""
    stored = {}

    async def fake_set(key, value, ex=None):
        stored[key] = value

    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(return_value=None)  # no prior history
    mock_redis.set = fake_set

    with patch("app.services.anti_tilt_service.get_redis", return_value=mock_redis):
        from app.services.anti_tilt_service import record_game_result

        await record_game_result("user_abc", won=True)

    assert "player:user_abc:recent_results" in stored
    results = json.loads(stored["player:user_abc:recent_results"])
    assert len(results) == 1
    assert results[0]["won"] is True


@pytest.mark.asyncio
async def test_three_consecutive_losses_triggers_override():
    """3 consecutive losses → get_bot_difficulty_override returns 'easy_heavy'."""
    history = [
        {"won": False, "timestamp": 1000.0},
        {"won": False, "timestamp": 2000.0},
        {"won": False, "timestamp": 3000.0},
    ]
    mock_redis = _make_redis_mock(_results_json(history))

    with patch("app.services.anti_tilt_service.get_redis", return_value=mock_redis):
        from app.services.anti_tilt_service import get_bot_difficulty_override

        override = await get_bot_difficulty_override("user_tilt")

    assert override == "easy_heavy"


@pytest.mark.asyncio
async def test_two_losses_no_override():
    """Only 2 consecutive losses → override is None (threshold is 3)."""
    history = [
        {"won": True, "timestamp": 1000.0},
        {"won": False, "timestamp": 2000.0},
        {"won": False, "timestamp": 3000.0},
    ]
    mock_redis = _make_redis_mock(_results_json(history))

    with patch("app.services.anti_tilt_service.get_redis", return_value=mock_redis):
        from app.services.anti_tilt_service import get_bot_difficulty_override

        override = await get_bot_difficulty_override("user_ok")

    assert override is None


@pytest.mark.asyncio
async def test_apply_easy_heavy_distribution():
    """When override='easy_heavy', ~80% of bots become 'easy'."""
    bots = [
        {"bot_name": f"bot_{i}", "difficulty": "hard", "avatar_id": "default_01"}
        for i in range(20)
    ]

    with patch("app.services.anti_tilt_service.get_redis"):
        from app.services.anti_tilt_service import apply_difficulty_override

        modified = await apply_difficulty_override(bots, override="easy_heavy")

    assert len(modified) == 20

    easy_count = sum(1 for b in modified if b["difficulty"] == "easy")
    medium_count = sum(1 for b in modified if b["difficulty"] == "medium")
    hard_count = sum(1 for b in modified if b["difficulty"] == "hard")

    # 80% of 20 = 16 easy, 15% = 3 medium, 5% = 1 hard (math.ceil rounding)
    # Allow ±1 tolerance for rounding edge cases
    assert easy_count >= 15, f"Expected ~16 easy bots, got {easy_count}"
    assert medium_count >= 2, f"Expected ~3 medium bots, got {medium_count}"
    assert easy_count + medium_count + hard_count == 20


@pytest.mark.asyncio
async def test_win_after_losses_resets_tilt():
    """A win after multiple losses resets the consecutive-loss counter to 0."""
    history = [
        {"won": False, "timestamp": 1000.0},
        {"won": False, "timestamp": 2000.0},
        {"won": True, "timestamp": 3000.0},  # win at the end
    ]
    mock_redis = _make_redis_mock(_results_json(history))

    with patch("app.services.anti_tilt_service.get_redis", return_value=mock_redis):
        from app.services.anti_tilt_service import get_consecutive_losses

        losses = await get_consecutive_losses("user_comeback")

    assert losses == 0


@pytest.mark.asyncio
async def test_redis_error_returns_none():
    """If Redis raises an exception, get_bot_difficulty_override returns None safely."""
    mock_redis = AsyncMock()
    mock_redis.get = AsyncMock(side_effect=ConnectionError("Redis down"))

    with patch("app.services.anti_tilt_service.get_redis", return_value=mock_redis):
        from app.services.anti_tilt_service import get_bot_difficulty_override

        override = await get_bot_difficulty_override("user_redis_fail")

    assert override is None
