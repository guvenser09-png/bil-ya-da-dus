"""CAP (Concurrent Active Players) Service.

Tracks real players currently in matchmaking to drive the
Adaptive Threshold System (AAS). Uses Redis Sorted Set.

Key: matchmaking:queue
Score: unix timestamp of when player joined queue
Window: 120 seconds (2 minutes)
"""

import logging
import time
from datetime import datetime, timezone

from app.config import settings
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_QUEUE_KEY = "matchmaking:queue"
_QUEUE_WINDOW_SECONDS = 120  # 2 minutes


async def add_to_queue(user_id: str) -> None:
    """Add a real player to the matchmaking queue with the current timestamp.

    Args:
        user_id: Unique identifier of the player joining the queue.
    """
    try:
        client = await get_redis()
        now = time.time()
        await client.zadd(_QUEUE_KEY, {user_id: now})
        # Expire the whole key after 3 windows to self-clean
        await client.expire(_QUEUE_KEY, _QUEUE_WINDOW_SECONDS * 3)
    except Exception:
        logger.exception("CAP: failed to add user %s to queue", user_id)


async def remove_from_queue(user_id: str) -> None:
    """Remove a player from the matchmaking queue.

    Args:
        user_id: Unique identifier of the player leaving the queue.
    """
    try:
        client = await get_redis()
        await client.zrem(_QUEUE_KEY, user_id)
    except Exception:
        logger.exception("CAP: failed to remove user %s from queue", user_id)


async def get_cap() -> int:
    """Return the number of real players active in matchmaking in the last 120 s.

    Returns:
        Integer count of active players, or 0 on Redis errors.
    """
    try:
        client = await get_redis()
        cutoff = time.time() - _QUEUE_WINDOW_SECONDS
        # Remove stale entries first, then count what remains
        await client.zremrangebyscore(_QUEUE_KEY, "-inf", cutoff)
        count = await client.zcard(_QUEUE_KEY)
        return int(count)
    except Exception:
        logger.exception("CAP: failed to get CAP, returning 0")
        return 0


async def get_min_real_players(
    user_games_played: int = 999,
    user_wait_seconds: float = 0.0,
) -> int:
    """Compute the minimum real-player threshold for this lobby resolution.

    AAS formula:
    1. New-player bypass  → if user_games_played < AAS_NEW_PLAYER_GAME_COUNT,
       always return 1 regardless of CAP.
    2. Night-mode penalty → if current TRT hour (UTC+3) is in [night_start, night_end),
       apply a -1 modifier to the CAP-derived level (floor at level 0).
    3. CAP levels         → determine base min_real:
         CAP  0-4   → level 0 → min_real 1
         CAP  5-19  → level 1 → min_real 2
         CAP  20-49 → level 2 → min_real 3
         CAP  50-99 → level 3 → min_real 4
         CAP 100+   → level 4 → min_real 5
    4. Long-wait discount → if user_wait_seconds > AAS_LONG_WAIT_THRESHOLD,
       reduce by 1 (floor at 1).

    Args:
        user_games_played: How many games this user has completed.
        user_wait_seconds: How long (s) the user has already been waiting.

    Returns:
        Minimum number of real players required to start the lobby (always >= 1).
    """
    # 1. New-player bypass
    if user_games_played < settings.AAS_NEW_PLAYER_GAME_COUNT:
        return 1

    # 2. Night mode check (TRT = UTC+3)
    trt_hour = datetime.now(timezone.utc).hour + 3
    trt_hour %= 24
    is_night = settings.AAS_NIGHT_START_HOUR <= trt_hour < settings.AAS_NIGHT_END_HOUR

    # 3. CAP → level → base min_real
    cap = await get_cap()

    if cap <= settings.AAS_LEVEL_0_MAX_CAP:
        level = 0
    elif cap <= settings.AAS_LEVEL_1_MAX_CAP:
        level = 1
    elif cap <= settings.AAS_LEVEL_2_MAX_CAP:
        level = 2
    elif cap <= settings.AAS_LEVEL_3_MAX_CAP:
        level = 3
    else:
        level = 4

    if is_night:
        level = max(0, level - 1)

    # level → min_real: level N maps to N+1 (level 0 → 1, level 4 → 5)
    min_real = level + 1

    # 4. Long-wait discount
    if user_wait_seconds > settings.AAS_LONG_WAIT_THRESHOLD:
        min_real = max(1, min_real - 1)

    return min_real


async def cleanup_stale_entries() -> None:
    """Remove all queue entries older than the 120-second window.

    Safe to call periodically (e.g., from a background task or Celery beat).
    """
    try:
        client = await get_redis()
        cutoff = time.time() - _QUEUE_WINDOW_SECONDS
        removed = await client.zremrangebyscore(_QUEUE_KEY, "-inf", cutoff)
        if removed:
            logger.debug("CAP cleanup: removed %d stale entries", removed)
    except Exception:
        logger.exception("CAP: cleanup_stale_entries failed")
