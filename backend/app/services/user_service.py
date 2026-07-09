"""User service — profile management, stats, search.

Business logic for user profile operations, separated from API endpoints.
"""

import logging
import uuid as uuid_mod
from datetime import datetime, timedelta, timezone

from jose import jwt
from sqlalchemy import and_, func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.utils.email_stub import send_email
from app.utils.profanity import contains_profanity
from app.utils.security import (
    decode_token,
    hash_password,
    revoke_all_refresh_tokens,
)

logger = logging.getLogger("app.user_service")

# Kısa ömürlü token tipleri (decode_token bunları expected_type ile doğrular)
RESET_TOKEN_TYPE = "reset"
VERIFY_TOKEN_TYPE = "verify"
RESET_TOKEN_EXPIRE_MINUTES = 30
VERIFY_TOKEN_EXPIRE_HOURS = 24


def _create_typed_token(user_id: str, token_type: str, expire: datetime) -> str:
    """Mevcut güvenlik desenine uygun, tipli kısa ömürlü JWT üret.

    security.py'deki create_*_token fonksiyonlarıyla aynı imza/alan yapısını
    kullanır; sadece 'type' alanı farklıdır (reset/verify).
    """
    payload = {
        "sub": user_id,
        "type": token_type,
        "exp": expire,
        "iat": datetime.now(timezone.utc),
        "jti": str(uuid_mod.uuid4()),
    }
    return jwt.encode(payload, settings.SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


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
    async def get_user_by_id_or_username(
        db: AsyncSession, identifier: str
    ) -> User | None:
        """UUID ya da username ile kullanıcı bul (herkese açık profil uçları için).

        Mobil bazı yerlerde username, bazı yerlerde UUID gönderir. Eskiden
        username gelince uuid.UUID(...) ValueError fırlatıp 500 dönüyordu;
        burada iki biçimi de destekleriz.
        """
        try:
            uid = _to_uuid(identifier)
        except (ValueError, AttributeError, TypeError):
            result = await db.execute(
                select(User).where(User.username == identifier)
            )
            return result.scalar_one_or_none()
        result = await db.execute(select(User).where(User.id == uid))
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

        # Validate avatar_id — tek karakter kaynağı CharacterService kataloğudur.
        # Karakter ücretsiz veya kullanıcı ona sahipse kuşanılabilir; pahalı bir
        # karakteri sahip olmadan kuşanmak (prestij hilesi) engellenir.
        if avatar_id is not None:
            # Yerel import: character_service, user_service'i import ettiği için
            # döngüsel importu önlemek üzere fonksiyon içinde yükleriz.
            from app.services.character_service import CharacterService

            if not CharacterService.exists(avatar_id):
                raise ValueError(f"Geçersiz karakter: {avatar_id}")
            if not await CharacterService.can_equip(db, user_id, avatar_id):
                raise ValueError("Bu karaktere sahip değilsin.")
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

        # HATA 6: best_rank = kullanıcının all-time sıralamadaki MEVCUT sırası.
        # leaderboard'daki composite ölçütle (total_score, games_won, id) birebir
        # aynı hesaplanır ki profildeki "#-" yerine doğru sıra gösterilsin.
        # Hiç oynamamışsa (games_played=0) sıralamaya dahil değildir → None.
        best_rank = None
        if user.games_played > 0:
            higher_stmt = (
                select(func.count())
                .select_from(User)
                .where(
                    User.is_active == True,  # noqa: E712
                    User.games_played > 0,
                    User.deleted_at.is_(None),
                    or_(
                        User.total_score > user.total_score,
                        and_(
                            User.total_score == user.total_score,
                            User.games_won > user.games_won,
                        ),
                        and_(
                            User.total_score == user.total_score,
                            User.games_won == user.games_won,
                            User.id < user.id,
                        ),
                    ),
                )
            )
            higher = (await db.scalar(higher_stmt)) or 0
            best_rank = int(higher) + 1

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
            "best_rank": best_rank,
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


    # --- Şifre sıfırlama (e-posta ile) ---

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> str | None:
        """Verilen e-postaya kayıtlı kullanıcı varsa reset token üret.

        Enumeration sızdırmamak için çağıran katman, kullanıcı olsa da olmasa
        da AYNI yanıtı dönmelidir. Burada kullanıcı yoksa None döneriz.
        Token DEV görünürlüğü için log'a da yazılır.
        """
        result = await db.execute(
            select(User).where(
                User.email == email,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()
        if not user:
            return None

        expire = datetime.now(timezone.utc) + timedelta(
            minutes=RESET_TOKEN_EXPIRE_MINUTES
        )
        token = _create_typed_token(str(user.id), RESET_TOKEN_TYPE, expire)

        logger.info("[PASSWORD RESET] user_id=%s için reset token üretildi.", user.id)

        await send_email(
            to=email,
            subject="Bil ya da Düş — Şifre Sıfırlama",
            body=(
                "Şifreni sıfırlamak için aşağıdaki kodu/bağlantıyı kullan "
                f"(30 dk geçerli):\n\n{token}\n\n"
                "Bu isteği sen yapmadıysan bu e-postayı yok sayabilirsin."
            ),
        )
        return token

    @staticmethod
    async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
        """Reset token'ı doğrula ve şifreyi güncelle.

        Tüm refresh token'lar geçersiz kılınır (güvenlik).

        Raises:
            ValueError: Token geçersiz/süresi dolmuş ya da kullanıcı yoksa.
        """
        payload = decode_token(token, expected_type=RESET_TOKEN_TYPE)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Geçersiz sıfırlama tokeni.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user or user.deleted_at is not None:
            raise ValueError("Kullanıcı bulunamadı.")

        user.password_hash = hash_password(new_password)
        await db.flush()

        # Tüm refresh token'ları geçersiz kıl (Redis)
        await revoke_all_refresh_tokens(user_id)

    # --- E-posta doğrulama ---

    @staticmethod
    async def send_verification_email(db: AsyncSession, user_id: str) -> str | None:
        """Giriş yapmış kullanıcı için doğrulama token'ı üret ve gönder.

        Returns:
            Üretilen token (DEV görünürlüğü için), kullanıcı yoksa None.

        Raises:
            ValueError: E-posta zaten doğrulanmışsa ya da e-posta yoksa.
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user or user.deleted_at is not None:
            return None

        if not user.email:
            raise ValueError("Hesabınızda doğrulanacak bir e-posta adresi yok.")

        if user.is_verified:
            raise ValueError("E-posta adresiniz zaten doğrulanmış.")

        expire = datetime.now(timezone.utc) + timedelta(
            hours=VERIFY_TOKEN_EXPIRE_HOURS
        )
        token = _create_typed_token(str(user.id), VERIFY_TOKEN_TYPE, expire)

        logger.info("[EMAIL VERIFY] user_id=%s için doğrulama token'ı üretildi.", user.id)

        await send_email(
            to=user.email,
            subject="Bil ya da Düş — E-posta Doğrulama",
            body=(
                "E-posta adresini doğrulamak için aşağıdaki kodu/bağlantıyı kullan "
                f"(24 saat geçerli):\n\n{token}"
            ),
        )
        return token

    @staticmethod
    async def verify_email(db: AsyncSession, token: str) -> User:
        """Doğrulama token'ını doğrula ve kullanıcıyı verified yap.

        Raises:
            ValueError: Token geçersiz/süresi dolmuş ya da kullanıcı yoksa.
        """
        payload = decode_token(token, expected_type=VERIFY_TOKEN_TYPE)
        user_id = payload.get("sub")
        if not user_id:
            raise ValueError("Geçersiz doğrulama tokeni.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user or user.deleted_at is not None:
            raise ValueError("Kullanıcı bulunamadı.")

        user.is_verified = True
        user.email_verified_at = datetime.now(timezone.utc)
        await db.flush()
        await db.refresh(user)
        return user

    # --- Hesap silme (KVKK/GDPR — soft-delete + anonimleştirme) ---

    @staticmethod
    async def delete_account(db: AsyncSession, user_id: str) -> None:
        """Hesabı KVKK/GDPR uyumlu şekilde sil (soft-delete + anonimleştirme).

        Kişisel veriler (e-posta, telefon, şifre, görünen isim, bio, avatar,
        ilgi alanları) temizlenir/anonimleştirilir; kayıt korunur ama hesap
        pasifleştirilir. Böylece oyun geçmişi/istatistik bütünlüğü bozulmaz
        ama kişisel veri saklanmaz. Silinen hesap login olamaz.

        Raises:
            ValueError: Kullanıcı yoksa ya da zaten silinmişse.
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user or user.deleted_at is not None:
            raise ValueError("Kullanıcı bulunamadı.")

        # username kolonu String(30); benzersiz ve 30 karaktere SIĞAN bir anonim
        # değer üret (uuid hex 32 hane → "del_" + ilk 26 hane = 30). Eski
        # "deleted_user_<uuid>" 49 karakterdi ve 500 (truncation) veriyordu.
        user.username = ("del_" + user.id.hex)[:30]
        user.email = None
        user.phone = None
        user.password_hash = None
        user.display_name = "Silinmiş Kullanıcı"
        user.bio = None
        user.avatar_id = "robot"
        user.interest_tags = None
        user.auth_provider = None
        user.auth_provider_id = None
        # Misafir bağını kopar: device_id unique olduğundan temizlenmezse aynı
        # cihaz bir daha misafir hesabı AÇAMAZ (unique ihlali) ya da silinmiş
        # hesaba bağlanırdı.
        user.device_id = None
        user.is_guest = False

        # Doğrulama / premium durumunu sıfırla
        user.is_verified = False
        user.email_verified_at = None
        user.is_premium = False
        user.premium_until = None

        # Hesabı pasifleştir + silme damgası
        user.is_active = False
        user.deleted_at = datetime.now(timezone.utc)

        await db.flush()

        # Tüm oturumları (refresh token) geçersiz kıl
        await revoke_all_refresh_tokens(user_id)


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
