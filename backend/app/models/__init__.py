"""SQLAlchemy models package — import all models here for Alembic auto-detection."""

from app.models.user import User
from app.models.game import Game, GameParticipant
from app.models.question import Question, QuestionHistory
from app.models.leaderboard import LeaderboardDaily, LeaderboardWeekly, LeaderboardSeasonal
from app.models.friendship import Friendship
from app.models.inventory import Transaction, InventoryItem

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
]
