"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.games import router as games_router
from app.api.leaderboard import router as leaderboard_router
from app.api.questions import router as questions_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(games_router, prefix="/games", tags=["Games"])
api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard"])
api_router.include_router(questions_router, prefix="/questions", tags=["Questions"])
