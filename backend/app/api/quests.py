"""Günlük 3 Görev uçları — ilerleme okuma + ödül alma."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services import quest_service
from app.utils.security import get_current_user_id

router = APIRouter()


@router.get("/today")
async def get_today_quests(
    user_id: str = Depends(get_current_user_id),
):
    """Bugünün 3 görevi: {date, quests:[{id,title,emoji,target,reward,progress,
    completed,claimed,claimable}], claimable_count, completed_count}.
    """
    return await quest_service.get_today(user_id)


@router.post("/{quest_id}/claim")
async def claim_quest(
    quest_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Tamamlanan görevin altınını al (günde bir kez, idempotent).

    Tamamlanmadıysa/zaten alındıysa 200 + {claimed: false, reason: ...} döner;
    görev bugün aktif değilse 404.
    """
    try:
        return await quest_service.claim(db, user_id, quest_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
