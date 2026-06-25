"""Anti-tilt service — secretly soften bot difficulty after consecutive losses.

After 3 consecutive losses, the next game's bot distribution shifts toward
easier bots. This is invisible to the player (no UI notification).

Storage: Redis key `player:{user_id}:recent_results` → JSON list of last 5 results
Each result: {"won": bool, "timestamp": float}
"""

import json
import logging
import time

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_RECENT_RESULTS_TTL = 604800  # 7 days
_MAX_RESULTS = 5
_TILT_THRESHOLD = 3  # consecutive losses required to trigger override


async def record_game_result(user_id: str, won: bool) -> None:
    """Append the result of a finished game to the player's recent results.

    Keeps only the last 5 results.

    Args:
        user_id: The player's unique identifier.
        won:     True if the player won this game.
    """
    key = f"player:{user_id}:recent_results"
    try:
        client = await get_redis()
        raw = await client.get(key)
        results: list[dict] = json.loads(raw) if raw else []
        results.append({"won": won, "timestamp": time.time()})
        # Keep only the most recent MAX_RESULTS entries
        results = results[-_MAX_RESULTS:]
        await client.set(key, json.dumps(results), ex=_RECENT_RESULTS_TTL)
    except Exception as exc:
        logger.warning("anti_tilt record_game_result failed for %s: %s", user_id, exc)


async def get_consecutive_losses(user_id: str) -> int:
    """Count the number of trailing consecutive losses in recent results.

    Returns:
        Number of consecutive losses at the end of the result list.
        0 if there are no results or any error.
    """
    key = f"player:{user_id}:recent_results"
    try:
        client = await get_redis()
        raw = await client.get(key)
        if not raw:
            return 0
        results: list[dict] = json.loads(raw)
        count = 0
        for entry in reversed(results):
            if entry.get("won"):
                break
            count += 1
        return count
    except Exception as exc:
        logger.warning("anti_tilt get_consecutive_losses failed for %s: %s", user_id, exc)
        return 0


async def get_bot_difficulty_override(user_id: str) -> str | None:
    """Return a difficulty override string if the player is tilting.

    Returns:
        "easy_heavy" if the player has 3+ consecutive losses,
        None otherwise (use normal distribution).
    """
    try:
        losses = await get_consecutive_losses(user_id)
        if losses >= _TILT_THRESHOLD:
            logger.info("Anti-tilt activated for user %s (%d consecutive losses)", user_id, losses)
            return "easy_heavy"
        return None
    except Exception as exc:
        logger.warning("anti_tilt get_bot_difficulty_override failed for %s: %s", user_id, exc)
        return None


async def apply_difficulty_override(
    bots: list[dict],
    override: str | None,
) -> list[dict]:
    """Redistribute bot difficulties if an override is active.

    When override="easy_heavy", bots are redistributed to:
        80% easy, 15% medium, 5% hard

    The returned list has the same length and structure as the input;
    only the "difficulty" field of each bot entry is modified.

    Args:
        bots:     List of bot dicts (each must have a "difficulty" key).
        override: Override string from get_bot_difficulty_override(), or None.

    Returns:
        Modified bots list (new list, input is not mutated).
    """
    if not override or override != "easy_heavy" or not bots:
        return list(bots)

    import math
    import random

    n = len(bots)
    easy_count = math.ceil(n * 0.80)
    medium_count = math.ceil(n * 0.15)
    hard_count = n - easy_count - medium_count

    # Clamp negatives that can arise from rounding with very small n
    hard_count = max(0, hard_count)
    if easy_count + medium_count + hard_count != n:
        easy_count = n - medium_count - hard_count

    difficulties = (
        ["easy"] * easy_count +
        ["medium"] * medium_count +
        ["hard"] * hard_count
    )
    random.shuffle(difficulties)

    modified = []
    for i, bot in enumerate(bots):
        new_bot = dict(bot)
        new_bot["difficulty"] = difficulties[i]
        modified.append(new_bot)

    return modified
