"""Game management endpoints — history, active games, leaderboard."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy import and_, desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.game import Game, GameParticipant, GameStatus
from app.models.user import User
from app.utils.security import get_current_user_id

router = APIRouter()


# --- Response schemas ---

class GameSummary(BaseModel):
    id: str
    status: str
    player_count: int
    bot_count: int
    current_round: int
    winner_username: str | None = None
    started_at: str
    ended_at: str | None = None

    model_config = {"from_attributes": True}


class GameHistoryItem(BaseModel):
    game_id: str
    score: int
    rounds_survived: int
    is_winner: bool
    played_at: str


class LeaderboardEntry(BaseModel):
    rank: int
    username: str
    display_name: str | None
    avatar_id: str
    total_score: int
    games_won: int
    games_played: int
    win_rate: float
    level: int


# --- Endpoints ---

@router.get("/history")
async def get_game_history(
    user_id: str = Depends(get_current_user_id),
    limit: int = Query(20, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's game history."""
    import uuid as uuid_mod

    stmt = (
        select(GameParticipant)
        .where(GameParticipant.user_id == uuid_mod.UUID(user_id))
        .order_by(GameParticipant.joined_at.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    participants = result.scalars().all()

    history = []
    for p in participants:
        game = p.game
        history.append({
            "game_id": str(p.game_id),
            "score": p.score,
            "rounds_survived": p.eliminated_at_round or 5,
            "is_winner": game.winner_id == uuid_mod.UUID(user_id) if game and game.winner_id else False,
            "played_at": p.joined_at.isoformat() if p.joined_at else None,
        })

    return {"history": history, "count": len(history)}


@router.get("/leaderboard")
async def get_leaderboard(
    period: str = Query("all", pattern=r"^(all|weekly|daily)$"),
    limit: int = Query(50, ge=1, le=100),
    db: AsyncSession = Depends(get_db),
):
    """Get the global leaderboard.

    Sorted by total_score descending.
    Periods: all (all time), weekly, daily.
    """
    stmt = (
        select(User)
        .where(
            and_(
                User.is_banned == False,  # noqa: E712
                User.is_active == True,   # noqa: E712
                User.games_played > 0,
            )
        )
        .order_by(User.total_score.desc())
        .limit(limit)
    )
    result = await db.execute(stmt)
    users = result.scalars().all()

    leaderboard = []
    for rank, user in enumerate(users, 1):
        leaderboard.append({
            "rank": rank,
            "username": user.username,
            "display_name": user.display_name,
            "avatar_id": user.avatar_id,
            "total_score": user.total_score,
            "games_won": user.games_won,
            "games_played": user.games_played,
            "win_rate": user.win_rate,
            "level": user.level,
        })

    return {"leaderboard": leaderboard, "total": len(leaderboard), "period": period}


@router.get("/active")
async def get_active_games(
    user_id: str = Depends(get_current_user_id),
):
    """Get currently active games."""
    from app.services.game_service import active_games

    games = []
    for game_id, engine in active_games.items():
        games.append({
            "game_id": game_id,
            "status": engine.status,
            "current_round": engine.current_round,
            "alive_count": engine.alive_count,
            "total_players": len(engine.players),
        })

    return {"active_games": games, "count": len(games)}
