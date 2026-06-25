"""Turnuva modu uçları (aylık ranked sezon).

PAY-TO-WIN YOK: giriş ücreti (altın) SINK olarak yanar ve PUAN VERMEZ.
Puan yalnızca maç performansından gelir (turnuva 3x çarpan). Ödüller
eksklüzif kozmetik + bonus altın + unvan.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.tournament_service import TournamentService
from app.utils.security import get_current_user_id

router = APIRouter()


class EnterRequest(BaseModel):
    currency: str = "gold"  # tek para birimi: altın (geriye dönük uyumluluk alanı)


@router.get("")
async def get_tournament(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Turnuva modu bilgisi: giriş seçenekleri, 3x çarpan, sezon + senin sıran."""
    try:
        return await TournamentService.info(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/enter")
async def enter_tournament(
    body: EnterRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Turnuvaya gir: altın düş. Yetersiz bakiyede 400."""
    try:
        return await TournamentService.enter(db, user_id, body.currency)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
