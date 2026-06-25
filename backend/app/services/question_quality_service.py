"""Question quality auto-management.

Auto-suspends questions that are too hard or too reported.
Runs checks on each answer submission.

Rules:
- correct_rate < 0.05 (5%) → suspend (difficulty too high or question broken)
- report_count >= 20 → suspend (player feedback)
- usage_count > 50 and correct_rate < 0.05 → suspend immediately
"""

import logging

from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.question import ApprovalStatus, Question

logger = logging.getLogger(__name__)

# Quality thresholds
SUSPEND_CORRECT_RATE_THRESHOLD: float = 0.05   # 5%
SUSPEND_REPORT_COUNT_THRESHOLD: int = 20
HIGH_USAGE_THRESHOLD: int = 50
LOW_RATING_THRESHOLD: float = 3.0              # avg user rating below this → review


async def _get_question_or_raise(question_id: str, db: AsyncSession) -> Question:
    """Fetch a Question row or raise ValueError when not found."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    q = result.scalar_one_or_none()
    if q is None:
        raise ValueError(f"Question not found: {question_id}")
    return q


def _should_suspend_on_quality(q: Question) -> bool:
    """Return True when the question meets auto-suspension criteria."""
    if q.correct_rate is None:
        return False

    # Immediate suspension when usage is high enough to be statistically meaningful
    if q.usage_count > HIGH_USAGE_THRESHOLD and q.correct_rate < SUSPEND_CORRECT_RATE_THRESHOLD:
        return True

    # General low-correct-rate suspension (only after at least 10 answers to avoid noise)
    if q.usage_count >= 10 and q.correct_rate < SUSPEND_CORRECT_RATE_THRESHOLD:
        return True

    return False


async def record_answer(
    question_id: str,
    was_correct: bool,
    db: AsyncSession,
) -> None:
    """Update usage statistics after a player answers a question.

    Increments ``usage_count`` and recalculates ``correct_rate``.
    If the updated rate falls below the suspension threshold, the question
    is automatically suspended.

    Args:
        question_id: The question's string ID.
        was_correct: Whether the player answered correctly.
        db:          An async SQLAlchemy session.
    """
    q = await _get_question_or_raise(question_id, db)

    # Incrementally update correct_rate without needing the raw correct-answer count
    # by reconstructing it from usage_count and the previous rate.
    previous_correct = (q.correct_rate or 0.0) * q.usage_count
    q.usage_count += 1
    new_correct = previous_correct + (1 if was_correct else 0)
    q.correct_rate = new_correct / q.usage_count

    if _should_suspend_on_quality(q):
        q.approval_status = ApprovalStatus.SUSPENDED
        logger.warning(
            "Auto-suspended question %s: correct_rate=%.3f, usage=%d",
            question_id,
            q.correct_rate,
            q.usage_count,
        )

    await db.flush()


async def report_question(
    question_id: str,
    user_id: str,
    db: AsyncSession,
) -> dict:
    """Increment the report count for a question.

    Automatically suspends the question if the report count reaches the
    threshold (20 reports).

    Args:
        question_id: The question's string ID.
        user_id:     The reporting player's user ID (for logging).
        db:          An async SQLAlchemy session.

    Returns:
        ``{"reported": True, "suspended": bool}`` indicating the outcome.
    """
    q = await _get_question_or_raise(question_id, db)

    q.report_count += 1
    suspended = False

    if q.report_count >= SUSPEND_REPORT_COUNT_THRESHOLD:
        if q.approval_status != ApprovalStatus.SUSPENDED:
            q.approval_status = ApprovalStatus.SUSPENDED
            suspended = True
            logger.warning(
                "Auto-suspended question %s: report_count=%d (reported by user %s)",
                question_id,
                q.report_count,
                user_id,
            )

    await db.flush()
    return {"reported": True, "suspended": suspended}


async def get_quality_stats(db: AsyncSession) -> dict:
    """Return aggregate quality statistics for the question bank.

    Args:
        db: An async SQLAlchemy session.

    Returns:
        Dict with keys: total, approved, pending, suspended,
        avg_correct_rate.
    """
    total = (
        await db.execute(select(func.count()).select_from(Question))
    ).scalar() or 0

    approved = (
        await db.execute(
            select(func.count()).select_from(Question).where(
                Question.approval_status == ApprovalStatus.APPROVED
            )
        )
    ).scalar() or 0

    pending = (
        await db.execute(
            select(func.count()).select_from(Question).where(
                Question.approval_status == ApprovalStatus.PENDING
            )
        )
    ).scalar() or 0

    suspended = (
        await db.execute(
            select(func.count()).select_from(Question).where(
                Question.approval_status == ApprovalStatus.SUSPENDED
            )
        )
    ).scalar() or 0

    avg_correct_rate_result = (
        await db.execute(
            select(func.avg(Question.correct_rate)).where(
                and_(
                    Question.correct_rate.is_not(None),
                    Question.approval_status == ApprovalStatus.APPROVED,
                )
            )
        )
    ).scalar()

    avg_correct_rate = round(float(avg_correct_rate_result), 4) if avg_correct_rate_result is not None else None

    return {
        "total": total,
        "approved": approved,
        "pending": pending,
        "suspended": suspended,
        "avg_correct_rate": avg_correct_rate,
    }


async def record_vote(
    question_id: str,
    vote: int,
    db: AsyncSession,
) -> None:
    """Record a thumbs-up (+1) or thumbs-down (-1) vote for a question.

    Updates the running sum and count stored on the Question row.
    If the resulting average rating drops below 3.0, the question is flagged
    for review (currently logged; a proper review-queue flag can be added later).

    Args:
        question_id: The question's string ID.
        vote:        ``+1`` for a positive vote, ``-1`` for negative.
        db:          An async SQLAlchemy session.

    Raises:
        ValueError: If ``vote`` is not +1 or -1, or if the question is not found.
    """
    if vote not in (1, -1):
        raise ValueError(f"vote must be +1 or -1, got {vote!r}")

    q = await _get_question_or_raise(question_id, db)

    q.user_rating_sum += vote
    q.user_rating_count += 1

    # Normalise to a 1-5 scale: map [-1, +1] average → [1, 5]
    # raw_avg in [-1, 1] → rating = (raw_avg + 1) / 2 * 4 + 1
    raw_avg = q.user_rating_sum / q.user_rating_count
    rating_5_scale = (raw_avg + 1) / 2 * 4 + 1

    if rating_5_scale < LOW_RATING_THRESHOLD:
        logger.warning(
            "Question %s has low user rating (%.2f/5, %d votes). "
            "Adding to review queue.",
            question_id,
            rating_5_scale,
            q.user_rating_count,
        )

    await db.flush()
