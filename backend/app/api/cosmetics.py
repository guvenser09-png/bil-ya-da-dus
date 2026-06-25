"""Kozmetik uçları — katalog listeleme, satın alma, kuşanma (COIN ile)."""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.cosmetics_service import CosmeticsService
from app.utils.security import get_current_user_id

router = APIRouter()


# --- İstek şemaları ---

class BuyCosmeticRequest(BaseModel):
    cosmetic_id: str


class EquipCosmeticRequest(BaseModel):
    slot: str
    cosmetic_id: str | None = None


# --- Uçlar ---

@router.get("")
async def get_cosmetics(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Kozmetik kataloğunu (owned bayraklarıyla), kuşanılmışları ve coin'i döner."""
    try:
        return await CosmeticsService.list_catalog(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        )


@router.post("/buy")
async def buy_cosmetic(
    body: BuyCosmeticRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Coin ile bir kozmetik satın alır."""
    try:
        return await CosmeticsService.buy(db, user_id, body.cosmetic_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )


@router.post("/equip")
async def equip_cosmetic(
    body: EquipCosmeticRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Sahip olunan bir kozmetiği ilgili slota kuşanır (null = çıkar)."""
    try:
        return await CosmeticsService.equip(
            db, user_id, body.slot, body.cosmetic_id
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        )
