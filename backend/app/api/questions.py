"""Question management endpoints (admin/internal)."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.question import ApprovalStatus, Question
from app.schemas.question import QuestionAdminResponse

router = APIRouter()


@router.get("/", response_model=list[QuestionAdminResponse])
async def list_questions(
    category: str | None = None,
    status_filter: ApprovalStatus | None = Query(None, alias="status"),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    db: AsyncSession = Depends(get_db),
):
    """List questions with optional filtering (admin endpoint)."""
    query = select(Question)

    if category:
        query = query.where(Question.category == category)
    if status_filter:
        query = query.where(Question.approval_status == status_filter)

    query = query.order_by(Question.created_at.desc()).offset(offset).limit(limit)
    result = await db.execute(query)
    questions = result.scalars().all()

    return [QuestionAdminResponse.model_validate(q) for q in questions]


@router.get("/{question_id}", response_model=QuestionAdminResponse)
async def get_question(question_id: str, db: AsyncSession = Depends(get_db)):
    """Get a single question by ID."""
    result = await db.execute(select(Question).where(Question.id == question_id))
    question = result.scalar_one_or_none()

    if not question:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Soru bulunamadı.",
        )

    return QuestionAdminResponse.model_validate(question)
