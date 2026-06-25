"""
Scheduled Celery tasks for QuizRoyale.

Tasks:
  - set_daily_challenge  : selects 5 questions and publishes them to Redis as today's challenge.
  - cleanup_lobbies      : removes lobbies that have been stuck in a non-active state too long.
  - snapshot_leaderboard : saves the current top-100 daily leaderboard to the DB before the midnight reset.
"""
import json
import logging
from datetime import date, datetime, timezone

from .celery_app import app

logger = logging.getLogger(__name__)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def set_daily_challenge(self):
    """
    Select 5 diverse questions (one per round type) and publish them to Redis
    under the key 'daily_challenge:<YYYY-MM-DD>'.
    """
    try:
        import redis
        from sqlalchemy import create_engine, text

        from app.core.config import settings

        engine = create_engine(settings.DATABASE_URL)
        r = redis.from_url(settings.REDIS_URL)

        today = date.today().isoformat()
        key = f"daily_challenge:{today}"

        # Skip if already set (idempotent)
        if r.exists(key):
            logger.info("Daily challenge already set for %s", today)
            return

        # Pull one question per round type from the question pool
        round_types = [
            ("dogru_yanlis", 1),
            ("gorsel", 1),
            ("karsilastirma", 1),
            ("coktan_secmeli", 1),
            ("tahmin", 1),
        ]

        selected = []
        with engine.connect() as conn:
            for q_type, _ in round_types:
                row = conn.execute(
                    text(
                        """
                        SELECT id, tip, soru, secenekler, dogru_cevap, sure_saniye, gorsel_url
                        FROM questions
                        WHERE tip = :tip
                          AND onay_durumu = 'onayli'
                          AND dogru_cevap_orani > 0.05
                        ORDER BY kullanim_sayisi ASC, RANDOM()
                        LIMIT 1
                        """
                    ),
                    {"tip": q_type},
                ).mappings().first()
                if row:
                    selected.append(dict(row))

        if len(selected) < 5:
            logger.warning(
                "Not enough questions for daily challenge: found %d", len(selected)
            )

        payload = {
            "date": today,
            "questions": selected,
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        # Expire at end of day + 1 hour buffer (90000 seconds)
        r.setex(key, 90000, json.dumps(payload))
        logger.info("Daily challenge set for %s with %d questions", today, len(selected))

    except Exception as exc:
        logger.error("set_daily_challenge failed: %s", exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=30)
def cleanup_lobbies(self):
    """
    Remove lobbies from Redis that have been in 'waiting' or 'cancelled' state
    for more than 5 minutes (stale lobbies after server restart, crashed games, etc.).
    """
    try:
        import redis

        from app.core.config import settings

        r = redis.from_url(settings.REDIS_URL)
        now = datetime.now(timezone.utc).timestamp()
        stale_threshold = 5 * 60  # 5 minutes in seconds

        # Lobbies are stored as lobby:<lobby_id>
        lobby_keys = r.keys("lobby:*")
        cleaned = 0

        for key in lobby_keys:
            raw = r.get(key)
            if not raw:
                continue
            try:
                lobby = json.loads(raw)
            except (json.JSONDecodeError, TypeError):
                r.delete(key)
                cleaned += 1
                continue

            status = lobby.get("status")
            created_at = lobby.get("created_at")

            if status in ("active", "finished"):
                continue

            if created_at:
                age = now - float(created_at)
                if age > stale_threshold:
                    r.delete(key)
                    cleaned += 1
                    logger.debug("Cleaned stale lobby %s (age %.0fs)", key, age)

        logger.info("cleanup_lobbies: removed %d stale lobbies", cleaned)
        return {"cleaned": cleaned}

    except Exception as exc:
        logger.error("cleanup_lobbies failed: %s", exc)
        raise self.retry(exc=exc)


@app.task(bind=True, max_retries=3, default_retry_delay=60)
def snapshot_leaderboard(self):
    """
    Persist the current top-100 daily leaderboard from Redis Sorted Set to
    the leaderboard_daily DB table before the midnight reset clears it.
    """
    try:
        import redis
        from sqlalchemy import create_engine, text

        from app.core.config import settings

        r = redis.from_url(settings.REDIS_URL)
        engine = create_engine(settings.DATABASE_URL)

        today = date.today().isoformat()
        redis_key = f"leaderboard:daily:{today}"

        # zrevrange returns list of (member, score) tuples
        top_100 = r.zrevrange(redis_key, 0, 99, withscores=True)

        if not top_100:
            logger.info("snapshot_leaderboard: no data in %s", redis_key)
            return {"saved": 0}

        rows = [
            {"user_id": member.decode(), "score": int(score), "date": today}
            for member, score in top_100
        ]

        with engine.begin() as conn:
            # Upsert — ignore duplicates (idempotent if run twice)
            conn.execute(
                text(
                    """
                    INSERT INTO leaderboard_daily (user_id, score, date)
                    VALUES (:user_id, :score, :date)
                    ON CONFLICT (user_id, date) DO UPDATE
                        SET score = EXCLUDED.score
                    """
                ),
                rows,
            )

        logger.info(
            "snapshot_leaderboard: saved %d entries for %s", len(rows), today
        )
        return {"saved": len(rows)}

    except Exception as exc:
        logger.error("snapshot_leaderboard failed: %s", exc)
        raise self.retry(exc=exc)
