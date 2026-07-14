"""Main API router — aggregates all sub-routers."""

from fastapi import APIRouter

from app.api.auth import router as auth_router
from app.api.users import router as users_router
from app.api.games import router as games_router
from app.api.leaderboard import router as leaderboard_router
from app.api.questions import router as questions_router
from app.api.store import router as store_router
from app.api.daily import router as daily_router
from app.api.cosmetics import router as cosmetics_router
from app.api.friends import router as friends_router
from app.api.season import router as season_router
from app.api.ads import router as ads_router
from app.api.tournament import router as tournament_router
from app.api.quests import router as quests_router

api_router = APIRouter()

api_router.include_router(auth_router, prefix="/auth", tags=["Authentication"])
api_router.include_router(users_router, prefix="/users", tags=["Users"])
api_router.include_router(games_router, prefix="/games", tags=["Games"])
api_router.include_router(leaderboard_router, prefix="/leaderboard", tags=["Leaderboard"])
api_router.include_router(questions_router, prefix="/questions", tags=["Questions"])
api_router.include_router(store_router, prefix="/store", tags=["Store"])
api_router.include_router(daily_router, prefix="/daily", tags=["Daily"])
api_router.include_router(cosmetics_router, prefix="/cosmetics", tags=["Cosmetics"])
api_router.include_router(friends_router, prefix="/friends", tags=["Friends"])
api_router.include_router(season_router, prefix="/season", tags=["Season"])
api_router.include_router(ads_router, prefix="/ads", tags=["Ads"])
api_router.include_router(tournament_router, prefix="/tournament", tags=["Tournament"])
api_router.include_router(quests_router, prefix="/quests", tags=["Quests"])
