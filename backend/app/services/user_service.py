"""User service — profile management, stats, search.

Business logic for user profile operations, separated from API endpoints.
"""

import uuid as uuid_mod

from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.utils.profanity import contains_profanity


def _to_uuid(user_id: str) -> uuid_mod.UUID:
    """Convert string user_id to UUID, handling both formats."""
    if isinstance(user_id, uuid_mod.UUID):
        return user_id
    return uuid_mod.UUID(str(user_id))


class UserService:
    """Handles user profile business logic."""

    @staticmethod
    async def get_user_by_id(db: AsyncSession, user_id: str) -> User | None:
        """Get a user by their UUID."""
        result = await db.execute(select(User).where(User.id == _to_uuid(user_id)))
        return result.scalar_one_or_none()

    @staticmethod
    async def update_profile(
        db: AsyncSession,
        user_id: str,
        display_name: str | None = None,
        avatar_id: str | None = None,
        bio: str | None = None,
        interest_tags: list[str] | None = None,
    ) -> User:
        """Update user profile with validation.

        Raises:
            ValueError: If profanity is found or user not found.
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        # Validate display_name
        if display_name is not None:
            if contains_profanity(display_name):
                raise ValueError("Görünen isim uygunsuz içerik barındırıyor.")
            user.display_name = display_name

        # Validate avatar_id
        if avatar_id is not None:
            if avatar_id not in VALID_AVATARS:
                raise ValueError(f"Geçersiz avatar ID: {avatar_id}")
            user.avatar_id = avatar_id

        # Validate bio
        if bio is not None:
            if contains_profanity(bio):
                raise ValueError("Biyografi uygunsuz içerik barındırıyor.")
            user.bio = bio

        # Validate interest tags
        if interest_tags is not None:
            if len(interest_tags) > 5:
                raise ValueError("En fazla 5 ilgi alanı etiketi eklenebilir.")
            for tag in interest_tags:
                if contains_profanity(tag):
                    raise ValueError(f"Etiket '{tag}' uygunsuz içerik barındırıyor.")
            user.interest_tags = interest_tags

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def search_users(
        db: AsyncSession,
        query: str,
        limit: int = 10,
        exclude_user_id: str | None = None,
    ) -> list[User]:
        """Search users by username or display name (partial match)."""
        search_pattern = f"%{query}%"
        stmt = (
            select(User)
            .where(
                or_(
                    User.username.ilike(search_pattern),
                    User.display_name.ilike(search_pattern),
                )
            )
            .where(User.is_banned == False)  # noqa: E712
            .where(User.is_active == True)   # noqa: E712
        )

        if exclude_user_id:
            stmt = stmt.where(User.id != _to_uuid(exclude_user_id))

        stmt = stmt.order_by(User.games_played.desc()).limit(limit)
        result = await db.execute(stmt)
        return list(result.scalars().all())

    @staticmethod
    async def get_user_stats(db: AsyncSession, user_id: str) -> dict:
        """Get detailed statistics for a user."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        accuracy = 0.0
        if user.total_questions_answered > 0:
            accuracy = round(
                user.total_correct_answers / user.total_questions_answered * 100, 1
            )

        return {
            "games_played": user.games_played,
            "games_won": user.games_won,
            "win_rate": user.win_rate,
            "total_score": user.total_score,
            "best_streak": user.best_streak,
            "total_correct_answers": user.total_correct_answers,
            "total_questions_answered": user.total_questions_answered,
            "accuracy_rate": accuracy,
            "favorite_category": user.favorite_category,
            "level": user.level,
            "xp": user.xp,
        }

    @staticmethod
    def calculate_level(xp: int) -> int:
        """Calculate player level from XP.

        Levels follow a quadratic curve:
        Level 1: 0 XP
        Level 2: 100 XP
        Level 3: 300 XP
        Level 4: 600 XP
        Level N: N*(N-1)*50 XP
        """
        level = 1
        while level * (level - 1) * 50 <= xp:
            level += 1
        return level - 1

    @staticmethod
    async def add_xp(db: AsyncSession, user_id: str, xp_amount: int) -> User:
        """Add XP to a user and recalculate their level."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        user.xp += xp_amount
        user.level = UserService.calculate_level(user.xp)
        await db.flush()
        return user

    @staticmethod
    async def update_game_stats(
        db: AsyncSession,
        user_id: str,
        won: bool,
        score: int,
        correct_answers: int,
        total_questions: int,
    ) -> User:
        """Update user stats after a game ends."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        user.games_played += 1
        if won:
            user.games_won += 1
        user.total_score += score
        user.total_correct_answers += correct_answers
        user.total_questions_answered += total_questions

        # Recalculate win rate
        if user.games_played > 0:
            user.win_rate = round(user.games_won / user.games_played * 100, 1)

        await db.flush()
        return user


# --- Valid avatar IDs ---
VALID_AVATARS = {
    # Default avatars (free)
    "default_01", "default_02", "default_03", "default_04", "default_05",
    "default_06", "default_07", "default_08", "default_09", "default_10",
    # Character avatars
    "char_astronaut", "char_pirate", "char_ninja", "char_robot", "char_wizard",
    "char_knight", "char_chef", "char_detective", "char_superhero", "char_musician",
    # Animal avatars
    "animal_cat", "animal_dog", "animal_panda", "animal_fox", "animal_owl",
    "animal_penguin", "animal_unicorn", "animal_dragon", "animal_koala", "animal_bear",
    # Seasonal (unlockable)
    "season_summer", "season_winter", "season_spring", "season_autumn",
}
