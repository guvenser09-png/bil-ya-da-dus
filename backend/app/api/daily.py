"""Günlük ödül + seri (streak) uçları."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.daily_service import DailyService
from app.utils.security import get_current_user_id

router = APIRouter()


@router.get("/status")
async def get_daily_status(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Günlük ödül durumunu döner.

    {can_claim, streak, today_reward, next_reward, last_claim_at}
    """
    try:
        return await DailyService.get_status(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )


@router.post("/claim")
async def claim_daily_reward(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Bugünkü günlük ödülü talep eder.

    Bugün alınmadıysa coin verir, seriyi günceller; alındıysa
    {claimed: false, reason: 'already_claimed', ...} döner.
    """
    try:
        return await DailyService.claim(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )
