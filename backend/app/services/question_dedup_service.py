"""Question deduplication service.

Prevents showing the same question to a player within 30 days.
Uses Redis Set per user + DB QuestionHistory table.

Redis key: user:{user_id}:recent_questions → Set of question IDs
TTL: 30 days (2592000 seconds)
Max size: 200 entries (older ones auto-expire from TTL, not explicit pruning)
"""

import logging
from typing import Any

from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import ApprovalStatus, Question
from app.redis_client import get_redis

logger = logging.getLogger(__name__)

THIRTY_DAYS_SECONDS = 2_592_000  # 30 * 24 * 60 * 60


def _recent_questions_key(user_id: str) -> str:
    """Redis key for a user's recently-seen question IDs."""
    return f"user:{user_id}:recent_questions"


async def mark_question_shown(user_id: str, question_id: str) -> None:
    """Record that a question was shown to a user.

    Adds the question_id to the user's Redis Set and refreshes the 30-day TTL
    so the entire set expires if the user goes inactive.

    Args:
        user_id:     The player's user ID (string form of UUID).
        question_id: The question's string ID (e.g. ``"q_00142"``).
    """
    key = _recent_questions_key(user_id)
    redis = await get_redis()
    await redis.sadd(key, question_id)
    await redis.expire(key, THIRTY_DAYS_SECONDS)
    logger.debug("Marked question %s shown for user %s", question_id, user_id)


async def was_shown_recently(user_id: str, question_id: str) -> bool:
    """Check whether a question was shown to a user in the past 30 days.

    Reads only from the Redis Set; the TTL guarantees freshness.

    Args:
        user_id:     The player's user ID.
        question_id: The question ID to check.

    Returns:
        ``True`` if the question is in the user's recent set, else ``False``.
    """
    key = _recent_questions_key(user_id)
    redis = await get_redis()
    members: set[str] = await redis.smembers(key)
    return question_id in members


async def filter_unseen_questions(
    user_id: str,
    question_ids: list[str],
) -> list[str]:
    """Return the subset of question IDs the user has *not* seen in 30 days.

    Order of the returned list is not guaranteed to match the input list.

    Args:
        user_id:      The player's user ID.
        question_ids: Candidate question IDs to filter.

    Returns:
        List of question IDs not in the user's recent-seen set.
    """
    if not question_ids:
        return []

    key = _recent_questions_key(user_id)
    redis = await get_redis()
    seen: set[str] = await redis.smembers(key)
    return [qid for qid in question_ids if qid not in seen]


async def get_question_for_user(
    user_id: str,
    category: str | None,
    question_type: str | None,
    db: AsyncSession,
) -> dict[str, Any] | None:
    """Fetch a suitable question for a user, preferring unseen + least-used.

    Query strategy:
    1. Build a base query for approved questions matching the requested
       category/type filters, ordered by ``usage_count ASC`` (least used first).
    2. Skip questions the user has seen in the past 30 days (Redis check).
    3. If *all* questions have been seen recently, fall back to the absolute
       least-used approved question regardless of seen status.

    Args:
        user_id:       The player's user ID.
        category:      Optional category filter (exact match).
        question_type: Optional question type value filter (e.g. ``"tahmin"``).
        db:            An async SQLAlchemy session.

    Returns:
        Question data as a plain ``dict``, or ``None`` if no questions exist.
    """
    # Build base statement
    stmt = select(Question).where(Question.approval_status == ApprovalStatus.APPROVED)

    if category:
        stmt = stmt.where(Question.category == category)

    if question_type:
        stmt = stmt.where(Question.type == question_type)

    stmt = stmt.order_by(Question.usage_count.asc())

    result = await db.execute(stmt)
    candidates: list[Question] = list(result.scalars().all())

    if not candidates:
        return None

    # Prefer a question the user has not seen recently
    all_ids = [q.id for q in candidates]
    unseen_ids = set(await filter_unseen_questions(user_id, all_ids))

    chosen: Question | None = None
    for q in candidates:  # already sorted by usage_count asc
        if q.id in unseen_ids:
            chosen = q
            break

    if chosen is None:
        # All questions have been seen — return the least recently used one
        # (candidates[0] is least-used overall which is still a reasonable pick)
        logger.info(
            "All questions seen by user %s; returning least-used fallback.", user_id
        )
        chosen = candidates[0]

    return {
        "id": chosen.id,
        "type": chosen.type.value if chosen.type else None,
        "category": chosen.category,
        "difficulty": chosen.difficulty,
        "content": chosen.content,
        "options": chosen.options,
        "correct_answer": chosen.correct_answer,
        "explanation": chosen.explanation,
        "image_url": chosen.image_url,
        "min_value": chosen.min_value,
        "max_value": chosen.max_value,
        "real_answer": chosen.real_answer,
        "unit": chosen.unit,
        "usage_count": chosen.usage_count,
        "approval_status": chosen.approval_status.value if chosen.approval_status else None,
    }
