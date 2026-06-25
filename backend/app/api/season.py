"""Battle Pass / Sezon uçları.

Koordinatör bu router'ı /season prefix ile bağlayacak (bkz. dosya sonu wiring notu).

Ödüller altın/kozmetik — pay-to-win YOK (bilgi avantajı değil).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.season_service import SeasonService
from app.utils.security import get_current_user_id

router = APIRouter()


# --- İstek şemaları ---

class ClaimRequest(BaseModel):
    tier: int
    track: str  # 'free' | 'premium'


# --- Uçlar ---

@router.get("")
async def get_season(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Mevcut sezonun durumu + kullanıcının ilerlemesi + tüm tier tablosu."""
    try:
        return await SeasonService.get_season(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/claim")
async def claim_reward(
    body: ClaimRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Ulaşılmış ve henüz alınmamış bir tier ödülünü claim et."""
    try:
        return await SeasonService.claim(
            db, user_id=user_id, tier=body.tier, track=body.track
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
