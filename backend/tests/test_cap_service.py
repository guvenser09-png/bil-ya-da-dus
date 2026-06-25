"""Unit tests for CAP (Concurrent Active Players) service.

All Redis interactions are mocked so no real Redis connection is needed.
"""

import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

import app.services.cap_service as cap_module
from app.services.cap_service import (
    _QUEUE_KEY,
    _QUEUE_WINDOW_SECONDS,
    add_to_queue,
    cleanup_stale_entries,
    get_cap,
    get_min_real_players,
    remove_from_queue,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_redis(zcard_return: int = 0) -> AsyncMock:
    """Build a minimal async Redis mock."""
    redis = AsyncMock()
    redis.zadd = AsyncMock(return_value=1)
    redis.zrem = AsyncMock(return_value=1)
    redis.zcard = AsyncMock(return_value=zcard_return)
    redis.zremrangebyscore = AsyncMock(return_value=0)
    redis.expire = AsyncMock(return_value=True)
    return redis


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAddAndGetCap:
    """test_add_and_get_cap — zadd is called with the right key and the
    CAP counter reflects the mocked zcard value."""

    @pytest.mark.asyncio
    async def test_add_and_get_cap(self):
        mock_redis = _make_redis(zcard_return=3)

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            await add_to_queue("user_abc")
            cap = await get_cap()

        mock_redis.zadd.assert_called_once()
        call_args = mock_redis.zadd.call_args
        assert call_args.args[0] == _QUEUE_KEY
        assert "user_abc" in call_args.args[1]

        assert cap == 3


class TestNewPlayerAlwaysOne:
    """test_cap_new_player_always_1 — a player with fewer than
    AAS_NEW_PLAYER_GAME_COUNT games always gets min_real=1."""

    @pytest.mark.asyncio
    async def test_cap_new_player_always_1(self):
        mock_redis = _make_redis(zcard_return=200)  # high CAP — should be ignored

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(user_games_played=3)

        assert result == 1


class TestCapLevel0ReturnsOne:
    """test_cap_level_0_returns_1 — when CAP is very low (0-4), base min_real=1."""

    @pytest.mark.asyncio
    async def test_cap_level_0_returns_1(self, monkeypatch):
        mock_redis = _make_redis(zcard_return=2)  # CAP=2 → level 0

        # Force a mid-day TRT hour to avoid night-mode interference
        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 12  # UTC noon → TRT 15:00
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(user_games_played=50, user_wait_seconds=0)

        assert result == 1


class TestCapLevel4ReturnsFive:
    """test_cap_level_4_returns_5 — when CAP is ≥100, base min_real=5."""

    @pytest.mark.asyncio
    async def test_cap_level_4_returns_5(self, monkeypatch):
        mock_redis = _make_redis(zcard_return=150)  # CAP=150 → level 4

        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 12  # midday UTC → no night mode
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(user_games_played=100, user_wait_seconds=0)

        assert result == 5


class TestLongWaitReducesThreshold:
    """test_long_wait_reduces_threshold — waiting longer than
    AAS_LONG_WAIT_THRESHOLD lowers the threshold by 1 (floor 1)."""

    @pytest.mark.asyncio
    async def test_long_wait_reduces_threshold(self, monkeypatch):
        # CAP=150 → level 4 → base min_real=5; long wait should bring it to 4
        mock_redis = _make_redis(zcard_return=150)

        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 12
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(
                user_games_played=100,
                user_wait_seconds=60,  # > AAS_LONG_WAIT_THRESHOLD (40)
            )

        assert result == 4

    @pytest.mark.asyncio
    async def test_long_wait_floor_at_one(self, monkeypatch):
        """Even with a long wait and level-0 CAP the result stays at 1."""
        mock_redis = _make_redis(zcard_return=1)  # CAP=1 → level 0 → base=1

        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 12
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(
                user_games_played=100,
                user_wait_seconds=999,
            )

        assert result == 1


class TestNightModeReducesThreshold:
    """test_night_mode_reduces_threshold — during TRT night hours the level
    drops by 1, so a level-2 CAP yields min_real=2 instead of 3."""

    @pytest.mark.asyncio
    async def test_night_mode_reduces_threshold(self, monkeypatch):
        # CAP=20 → level 2 → base min_real=3; night mode → level 1 → min_real=2
        mock_redis = _make_redis(zcard_return=20)

        # TRT hour = UTC hour + 3; we want TRT=3 (within 2-8 window)
        # So UTC hour must be 0 (midnight UTC = 03:00 TRT)
        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 0  # UTC midnight → TRT 03:00
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            result = await get_min_real_players(user_games_played=100, user_wait_seconds=0)

        assert result == 2


class TestCleanupStaleEntries:
    """test_cleanup_stale_entries — zremrangebyscore is called with a cutoff
    120 seconds in the past."""

    @pytest.mark.asyncio
    async def test_cleanup_stale_entries(self):
        mock_redis = _make_redis()
        mock_redis.zremrangebyscore = AsyncMock(return_value=5)

        before = time.time()
        with patch("app.services.cap_service.get_redis", return_value=mock_redis):
            await cleanup_stale_entries()
        after = time.time()

        mock_redis.zremrangebyscore.assert_called_once()
        call_args = mock_redis.zremrangebyscore.call_args.args
        assert call_args[0] == _QUEUE_KEY
        assert call_args[1] == "-inf"
        cutoff = call_args[2]
        # cutoff should be approximately (now - 120)
        assert before - _QUEUE_WINDOW_SECONDS - 1 <= cutoff <= after - _QUEUE_WINDOW_SECONDS + 1


class TestRedisErrorReturnsDefault:
    """test_redis_error_returns_default — when Redis raises, get_cap returns 0
    and get_min_real_players returns a safe default (1)."""

    @pytest.mark.asyncio
    async def test_get_cap_redis_error_returns_zero(self):
        broken_redis = AsyncMock()
        broken_redis.zremrangebyscore = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.services.cap_service.get_redis", return_value=broken_redis):
            cap = await get_cap()

        assert cap == 0

    @pytest.mark.asyncio
    async def test_get_min_real_redis_error_returns_one(self, monkeypatch):
        """When get_cap() fails (returns 0), new-player rule or level-0 cap
        ensures the result is still ≥ 1."""
        broken_redis = AsyncMock()
        broken_redis.zremrangebyscore = AsyncMock(side_effect=ConnectionError("Redis down"))

        import datetime as dt_mod
        fixed_dt = MagicMock()
        fixed_dt.hour = 12
        monkeypatch.setattr(
            "app.services.cap_service.datetime",
            MagicMock(now=MagicMock(return_value=fixed_dt)),
        )

        with patch("app.services.cap_service.get_redis", return_value=broken_redis):
            result = await get_min_real_players(user_games_played=999, user_wait_seconds=0)

        # CAP=0 → level 0 → min_real=1
        assert result >= 1

    @pytest.mark.asyncio
    async def test_add_to_queue_redis_error_silent(self):
        """add_to_queue should not raise even when Redis is unavailable."""
        broken_redis = AsyncMock()
        broken_redis.zadd = AsyncMock(side_effect=ConnectionError("Redis down"))

        with patch("app.services.cap_service.get_redis", return_value=broken_redis):
            # Should not raise
            await add_to_queue("ghost_user")
