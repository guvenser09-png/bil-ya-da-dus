"""Daily Challenge service — same 5 questions for all players on a given day.

Each day at midnight TRT (UTC+3), a new set of 5 questions is selected.
Players can play the daily challenge once per day.
Scores go to a separate leaderboard, not the main one.

Redis keys:
- daily_challenge:{YYYY-MM-DD}           → JSON list of 5 question dicts (TTL 48h)
- daily_challenge_played:{user_id}:{YYYY-MM-DD} → "1" (TTL 48h, marks as played)
- daily_challenge_score:{YYYY-MM-DD}     → Sorted Set {user_id: score} (TTL 8 days)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_TRT_ZONE = ZoneInfo("Europe/Istanbul")  # UTC+3
_QUESTIONS_TTL = 172800   # 48 hours
_PLAYED_TTL = 172800      # 48 hours
_LEADERBOARD_TTL = 691200  # 8 days


# ---------------------------------------------------------------------------
# Internal helper — same mock questions used in game.py
# ---------------------------------------------------------------------------

def _get_fallback_questions() -> list[dict]:
    """Return a set of 5 questions for daily challenge when no DB is available."""
    return [
        {
            "id": "daily_1",
            "type": "dogru_yanlis",
            "content": "İstanbul Türkiye'nin en kalabalık şehridir.",
            "question": "İstanbul Türkiye'nin en kalabalık şehridir.",
            "options": ["Doğru", "Yanlış"],
            "correct_answer": 0,
            "time_seconds": 5,
        },
        {
            "id": "daily_2",
            "type": "gorsel",
            "content": "Bu hangi ülkenin bayrağıdır?",
            "question": "Bu hangi ülkenin bayrağıdır?",
            "options": ["Türkiye", "Azerbaycan", "Kıbrıs", "Özbekistan"],
            "correct_answer": 0,
            "time_seconds": 7,
        },
        {
            "id": "daily_3",
            "type": "karsilastirma",
            "content": "Hangisi daha büyük bir şehir?",
            "question": "Hangisi daha büyük bir şehir?",
            "options": ["Ankara", "İzmir"],
            "correct_answer": 0,
            "time_seconds": 7,
        },
        {
            "id": "daily_4",
            "type": "coktan_secmeli",
            "content": "Türkiye'nin resmi dili hangisidir?",
            "question": "Türkiye'nin resmi dili hangisidir?",
            "options": ["Kürtçe", "Türkçe", "Arapça", "Farsça"],
            "correct_answer": 1,
            "time_seconds": 8,
        },
        {
            "id": "daily_5",
            "type": "tahmin",
            "content": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "question": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "options": None,
            "correct_answer": 85,
            "real_answer": 85,
            "min_value": 50,
            "max_value": 120,
            "unit": "milyon",
            "time_seconds": 8,
        },
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_today_key() -> str:
    """Return today's date string in TRT timezone (YYYY-MM-DD).

    TRT is UTC+3. The daily challenge resets at midnight Istanbul time.
    """
    now_trt = datetime.now(tz=_TRT_ZONE)
    return now_trt.strftime("%Y-%m-%d")


async def get_today_questions() -> list[dict]:
    """Return today's 5 questions, generating and caching them if not set.

    Questions are shared across all players on the same day.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge:{date_key}"
    try:
        client = await get_redis()
        raw = await client.get(redis_key)
        if raw:
            return json.loads(raw)

        # Not cached yet — generate and cache
        questions = _get_fallback_questions()
        await set_today_questions(questions)
        return questions
    except Exception as exc:
        logger.warning("daily_challenge get_today_questions failed: %s", exc)
        return _get_fallback_questions()


async def set_today_questions(questions: list[dict]) -> None:
    """Cache today's questions to Redis with a 48-hour TTL.

    Args:
        questions: List of 5 question dicts to cache.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge:{date_key}"
    try:
        client = await get_redis()
        await client.set(redis_key, json.dumps(questions), ex=_QUESTIONS_TTL)
    except Exception as exc:
        logger.warning("daily_challenge set_today_questions failed: %s", exc)


async def has_played_today(user_id: str) -> bool:
    """Check if the user has already played today's daily challenge.

    Returns:
        True if the user played today, False otherwise.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge_played:{user_id}:{date_key}"
    try:
        client = await get_redis()
        return await client.exists(redis_key) > 0
    except Exception as exc:
        logger.warning("daily_challenge has_played_today failed for %s: %s", user_id, exc)
        return False


async def mark_as_played(user_id: str) -> None:
    """Record that the user has completed today's daily challenge.

    Sets a 48-hour TTL flag so the record expires naturally.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge_played:{user_id}:{date_key}"
    try:
        client = await get_redis()
        await client.set(redis_key, "1", ex=_PLAYED_TTL)
    except Exception as exc:
        logger.warning("daily_challenge mark_as_played failed for %s: %s", user_id, exc)


async def submit_score(user_id: str, score: int) -> int:
    """Add the player's score to today's daily challenge leaderboard.

    Args:
        user_id: The player's unique identifier.
        score:   The score achieved in the daily challenge.

    Returns:
        The player's 1-based rank after submission (1 = highest score).
    """
    date_key = await get_today_key()
    leaderboard_key = f"daily_challenge_score:{date_key}"
    try:
        client = await get_redis()
        # ZADD with score; higher score = better rank (use positive score)
        await client.zadd(leaderboard_key, {user_id: score})
        await client.expire(leaderboard_key, _LEADERBOARD_TTL)

        # Rank: count players with strictly higher score + 1
        # Redis ZREVRANK gives 0-based descending rank
        rank_zero = await client.zrevrank(leaderboard_key, user_id)
        return (rank_zero + 1) if rank_zero is not None else 1
    except Exception as exc:
        logger.warning("daily_challenge submit_score failed for %s: %s", user_id, exc)
        return 0


async def get_daily_leaderboard(limit: int = 100) -> list[dict]:
    """Return the top N players for today's daily challenge.

    Returns:
        List of dicts with keys: rank, user_id, score.
        Ordered by score descending (rank 1 = best).
    """
    date_key = await get_today_key()
    leaderboard_key = f"daily_challenge_score:{date_key}"
    try:
        client = await get_redis()
        # ZREVRANGE with scores, highest first
        entries = await client.zrevrange(leaderboard_key, 0, limit - 1, withscores=True)
        result = []
        for rank, (uid, score) in enumerate(entries, start=1):
            result.append({
                "rank": rank,
                "user_id": uid,
                "score": int(score),
            })
        return result
    except Exception as exc:
        logger.warning("daily_challenge get_daily_leaderboard failed: %s", exc)
        return []
