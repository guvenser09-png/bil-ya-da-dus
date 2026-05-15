"""Question management endpoints — generate, list, approve, stats."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.question_service import CATEGORIES, QuestionService
from app.utils.security import get_current_user_id

router = APIRouter()


# --- Request/Response schemas ---

class QuestionGenerateRequest(BaseModel):
    question_type: str = Field(..., pattern=r"^(dogru_yanlis|gorsel|karsilastirma|coktan_secmeli|tahmin)$")
    category: str = Field(default="Genel Kültür")
    difficulty: int = Field(default=3, ge=1, le=5)
    count: int = Field(default=5, ge=1, le=20)


class QuestionResponse(BaseModel):
    id: str
    type: str
    category: str
    difficulty: int
    content: str
    options: dict | list | None
    correct_answer: int | None
    explanation: str | None
    approval_status: str
    min_value: float | None = None
    max_value: float | None = None
    real_answer: float | None = None
    unit: str | None = None

    model_config = {"from_attributes": True}


class QuestionApproveRequest(BaseModel):
    question_id: str


class QuestionStatsResponse(BaseModel):
    total: int
    approved: int
    pending: int
    rejected: int
    by_type: dict[str, int]


# --- Endpoints ---

@router.post("/generate", response_model=list[QuestionResponse], status_code=201)
async def generate_questions(
    request: QuestionGenerateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Generate new questions using AI (or seed data).

    Questions are created with 'pending' approval status.
    """
    raw_questions = await QuestionService.generate_questions_ai(
        question_type=request.question_type,
        category=request.category,
        difficulty=request.difficulty,
        count=request.count,
    )

    if not raw_questions:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Soru üretilemedi.",
        )

    saved = await QuestionService.save_questions(
        db=db,
        questions=raw_questions,
        question_type=request.question_type,
    )

    return [QuestionResponse.model_validate(q) for q in saved]


@router.get("/stats", response_model=QuestionStatsResponse)
async def get_question_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get statistics about the question bank."""
    stats = await QuestionService.get_question_stats(db)
    return stats


@router.post("/approve/{question_id}", response_model=QuestionResponse)
async def approve_question(
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Approve a pending question."""
    q = await QuestionService.approve_question(db, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    return QuestionResponse.model_validate(q)


@router.post("/reject/{question_id}", response_model=QuestionResponse)
async def reject_question(
    question_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Reject a pending question."""
    q = await QuestionService.reject_question(db, question_id)
    if not q:
        raise HTTPException(status_code=404, detail="Soru bulunamadı.")
    return QuestionResponse.model_validate(q)


@router.post("/approve-all")
async def approve_all_pending(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Approve all pending questions (admin action)."""
    count = await QuestionService.bulk_approve_all_pending(db)
    return {"message": f"{count} soru onaylandı.", "approved_count": count}


@router.post("/seed")
async def seed_questions(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Seed the database with initial questions for all round types.

    Generates and auto-approves ~40 questions across all categories.
    """
    total_saved = 0
    types = ["dogru_yanlis", "gorsel", "karsilastirma", "coktan_secmeli", "tahmin"]

    for q_type in types:
        for category in ["Genel Kültür", "Bilim", "Tarih"]:
            raw = await QuestionService.generate_questions_ai(
                question_type=q_type,
                category=category,
                difficulty=3,
                count=5,
            )
            if raw:
                saved = await QuestionService.save_questions(db, raw, q_type, source="seed")
                total_saved += len(saved)

    # Auto-approve all seeded questions
    approved = await QuestionService.bulk_approve_all_pending(db)

    return {
        "message": f"{total_saved} soru oluşturuldu, {approved} soru onaylandı.",
        "total_generated": total_saved,
        "total_approved": approved,
    }


@router.get("/categories")
async def get_categories():
    """Get available question categories."""
    return {"categories": CATEGORIES}
