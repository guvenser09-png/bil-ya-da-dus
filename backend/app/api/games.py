"""Game history endpoints."""

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game, GameParticipant
from app.schemas.game import GameHistoryResponse, GameResponse
from app.utils.security import get_current_user_id

router = APIRouter()


@router.get("/history", response_model=GameHistoryResponse)
async def get_game_history(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's game history."""
    # Count total games
    count_query = (
        select(func.count())
        .select_from(GameParticipant)
        .where(GameParticipant.user_id == user_id)
    )
    total = (await db.execute(count_query)).scalar() or 0

    # Get paginated games
    games_query = (
        select(Game)
        .join(GameParticipant, GameParticipant.game_id == Game.id)
        .where(GameParticipant.user_id == user_id)
        .order_by(Game.started_at.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    )
    result = await db.execute(games_query)
    games = result.scalars().all()

    return GameHistoryResponse(
        games=[GameResponse.model_validate(g) for g in games],
        total=total,
        page=page,
        page_size=page_size,
    )
