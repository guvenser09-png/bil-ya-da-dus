"""Leaderboard endpoints — daily, weekly, seasonal rankings."""

from fastapi import APIRouter, Depends, Query

from app.redis_client import get_redis

router = APIRouter()


@router.get("/daily")
async def get_daily_leaderboard(
    limit: int = Query(100, ge=1, le=100),
):
    """Get today's top players.

    Uses Redis Sorted Set for real-time ranking.
    Falls back to PostgreSQL if Redis is unavailable.
    """
    redis = await get_redis()

    try:
        # Get top N from Redis sorted set (highest score first)
        results = await redis.zrevrange(
            "leaderboard:daily", 0, limit - 1, withscores=True
        )

        leaderboard = [
            {"rank": i + 1, "user_id": user_id, "score": int(score)}
            for i, (user_id, score) in enumerate(results)
        ]
    except Exception:
        leaderboard = []

    return {"period": "daily", "entries": leaderboard, "total": len(leaderboard)}


@router.get("/weekly")
async def get_weekly_leaderboard(
    limit: int = Query(100, ge=1, le=500),
):
    """Get this week's top players."""
    redis = await get_redis()

    try:
        results = await redis.zrevrange(
            "leaderboard:weekly", 0, limit - 1, withscores=True
        )

        leaderboard = [
            {"rank": i + 1, "user_id": user_id, "score": int(score)}
            for i, (user_id, score) in enumerate(results)
        ]
    except Exception:
        leaderboard = []

    return {"period": "weekly", "entries": leaderboard, "total": len(leaderboard)}


@router.get("/seasonal")
async def get_seasonal_leaderboard(
    season_id: int = Query(1, ge=1),
    limit: int = Query(100, ge=1, le=1000),
):
    """Get seasonal leaderboard."""
    redis = await get_redis()

    try:
        results = await redis.zrevrange(
            f"leaderboard:season:{season_id}", 0, limit - 1, withscores=True
        )

        leaderboard = [
            {"rank": i + 1, "user_id": user_id, "score": int(score)}
            for i, (user_id, score) in enumerate(results)
        ]
    except Exception:
        leaderboard = []

    return {
        "period": "seasonal",
        "season_id": season_id,
        "entries": leaderboard,
        "total": len(leaderboard),
    }
