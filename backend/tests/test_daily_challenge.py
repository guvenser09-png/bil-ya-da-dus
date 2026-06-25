"""Tests for app/services/daily_challenge_service.py — 5 scenarios."""

import json
import re
from unittest.mock import AsyncMock, patch

import pytest


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis_mock(**overrides) -> AsyncMock:
    """Build an AsyncMock with sensible defaults for Redis operations."""
    mock = AsyncMock()
    mock.get = AsyncMock(return_value=None)
    mock.set = AsyncMock()
    mock.exists = AsyncMock(return_value=0)
    mock.zadd = AsyncMock()
    mock.expire = AsyncMock()
    mock.zrevrank = AsyncMock(return_value=0)   # default rank 0 → returns 1
    mock.zrevrange = AsyncMock(return_value=[])
    for attr, value in overrides.items():
        setattr(mock, attr, value)
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_get_today_key_format():
    """get_today_key returns a string in YYYY-MM-DD format."""
    from app.services.daily_challenge_service import get_today_key

    key = await get_today_key()

    # Must match ISO date pattern
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", key), f"Unexpected key format: {key!r}"
    # Sanity: year must be current era
    year = int(key[:4])
    assert 2020 <= year <= 2100


@pytest.mark.asyncio
async def test_has_not_played_returns_false():
    """has_played_today returns False when Redis has no record for the user."""
    mock_redis = _make_redis_mock()
    mock_redis.exists = AsyncMock(return_value=0)

    with patch("app.services.daily_challenge_service.get_redis", return_value=mock_redis):
        from app.services.daily_challenge_service import has_played_today

        result = await has_played_today("user_new")

    assert result is False


@pytest.mark.asyncio
async def test_mark_and_check_played():
    """After mark_as_played, has_played_today returns True."""
    store: dict[str, str] = {}

    async def fake_set(key, value, ex=None):
        store[key] = value

    async def fake_exists(key):
        return 1 if key in store else 0

    mock_redis = _make_redis_mock()
    mock_redis.set = fake_set
    mock_redis.exists = fake_exists

    with patch("app.services.daily_challenge_service.get_redis", return_value=mock_redis):
        from app.services.daily_challenge_service import has_played_today, mark_as_played

        assert await has_played_today("user_mark") is False
        await mark_as_played("user_mark")
        assert await has_played_today("user_mark") is True


@pytest.mark.asyncio
async def test_submit_score_returns_rank():
    """submit_score returns the correct 1-based rank from Redis ZREVRANK."""
    # Simulate: 3 players ahead → rank 4 (zrevrank returns 3)
    mock_redis = _make_redis_mock()
    mock_redis.zadd = AsyncMock()
    mock_redis.expire = AsyncMock()
    mock_redis.zrevrank = AsyncMock(return_value=3)  # 0-based → rank 4

    with patch("app.services.daily_challenge_service.get_redis", return_value=mock_redis):
        from app.services.daily_challenge_service import submit_score

        rank = await submit_score("user_scorer", score=250)

    assert rank == 4
    mock_redis.zadd.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_leaderboard_ordered():
    """get_daily_leaderboard returns entries ordered by rank with correct fields."""
    # Simulate zrevrange returning tuples (user_id, score) highest first
    fake_entries = [
        ("user_gold", 300.0),
        ("user_silver", 250.0),
        ("user_bronze", 200.0),
    ]
    mock_redis = _make_redis_mock()
    mock_redis.zrevrange = AsyncMock(return_value=fake_entries)

    with patch("app.services.daily_challenge_service.get_redis", return_value=mock_redis):
        from app.services.daily_challenge_service import get_daily_leaderboard

        leaderboard = await get_daily_leaderboard(limit=10)

    assert len(leaderboard) == 3

    # Check ordering and field presence
    assert leaderboard[0]["rank"] == 1
    assert leaderboard[0]["user_id"] == "user_gold"
    assert leaderboard[0]["score"] == 300

    assert leaderboard[1]["rank"] == 2
    assert leaderboard[1]["user_id"] == "user_silver"
    assert leaderboard[1]["score"] == 250

    assert leaderboard[2]["rank"] == 3
    assert leaderboard[2]["user_id"] == "user_bronze"
    assert leaderboard[2]["score"] == 200
