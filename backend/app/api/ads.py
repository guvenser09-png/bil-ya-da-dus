"""Ödüllü reklam ödülü uçları.

İstemci bir ödüllü reklamı izlediğinde bu uca gelir; backend güvenli şekilde
SADECE coin/kozmetik ödülü verir (pay-to-win YOK). Anti-fraud: günlük limit,
placement başına cap ve nonce idempotency.
"""

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.ads_service import ADS_DAILY_LIMIT, PLACEMENTS, AdsService
from app.utils.security import get_current_user_id

router = APIRouter()


class AdRewardRequest(BaseModel):
    placement: str  # 'daily_coins' | 'double_match' | 'shop_bonus'
    # İstemci tarafından üretilen tek seferlik kimlik (idempotency).
    nonce: str | None = None


@router.get("/placements")
async def list_placements():
    """Tanımlı reklam yerleşimleri + ödülleri + günlük limit bilgisi."""
    return {
        "daily_limit": ADS_DAILY_LIMIT,
        "placements": {
            k: {"reward": v["reward"], "daily_cap": v["daily_cap"]}
            for k, v in PLACEMENTS.items()
        },
    }


@router.post("/reward")
async def reward(
    body: AdRewardRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Ödüllü reklam ödülünü ver. Ödül SADECE coin (pay-to-win YOK).

    Anti-fraud: günlük toplam limit + placement başına cap + nonce idempotency.
    """
    try:
        return await AdsService.grant_reward(
            db, user_id=user_id, placement=body.placement, nonce=body.nonce
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
