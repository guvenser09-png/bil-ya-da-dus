"""SQLAlchemy models package — import all models here for Alembic auto-detection."""

from app.models.user import User
from app.models.game import Game, GameParticipant
from app.models.question import Question, QuestionHistory
from app.models.leaderboard import LeaderboardDaily, LeaderboardWeekly, LeaderboardSeasonal
from app.models.friendship import Friendship
from app.models.inventory import Transaction, InventoryItem
from app.models.purchase import Purchase, Entitlement
from app.models.cosmetic import UserCosmetic
from app.models.tournament import SeasonScore, SeasonSettlement

__all__ = [
    "User",
    "Game",
    "GameParticipant",
    "Question",
    "QuestionHistory",
    "LeaderboardDaily",
    "LeaderboardWeekly",
    "LeaderboardSeasonal",
    "Friendship",
    "Transaction",
    "InventoryItem",
    "Purchase",
    "Entitlement",
    "UserCosmetic",
    "SeasonScore",
    "SeasonSettlement",
]
