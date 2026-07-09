"""Authentication service — user registration, login, token management.

Handles all auth business logic, separating it from API endpoint code.
"""

import secrets
import uuid as uuid_mod
from datetime import datetime, timezone

from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.user import User
from app.utils.security import (
    create_access_token,
    create_password_reset_token,
    create_refresh_token,
    decode_token,
    hash_password,
    is_refresh_token_valid,
    revoke_all_refresh_tokens,
    revoke_refresh_token,
    store_refresh_token,
    verify_password,
)


class AuthService:
    """Handles authentication business logic."""

    @staticmethod
    async def register(
        db: AsyncSession,
        username: str,
        password: str,
        email: str | None = None,
        phone: str | None = None,
        display_name: str | None = None,
    ) -> tuple[User, str, str]:
        """Register a new user. Returns (user, access_token, refresh_token)."""
        # Check username uniqueness
        result = await db.execute(
            select(User).where(User.username == username)
        )
        if result.scalar_one_or_none():
            raise ValueError("Bu kullanıcı adı zaten alınmış.")

        # Check email uniqueness
        if email:
            result = await db.execute(
                select(User).where(User.email == email)
            )
            if result.scalar_one_or_none():
                raise ValueError("Bu e-posta adresi zaten kayıtlı.")

        # Check phone uniqueness
        if phone:
            result = await db.execute(
                select(User).where(User.phone == phone)
            )
            if result.scalar_one_or_none():
                raise ValueError("Bu telefon numarası zaten kayıtlı.")

        # Create user
        user = User(
            username=username,
            email=email,
            phone=phone,
            password_hash=hash_password(password),
            display_name=display_name or username,
            auth_provider="email",
        )
        db.add(user)
        await db.flush()
        await db.refresh(user)

        # Generate tokens
        access_token = create_access_token(user_id=str(user.id))
        refresh_token = create_refresh_token(user_id=str(user.id))

        # Store refresh token in Redis
        refresh_payload = decode_token(refresh_token, expected_type="refresh")
        refresh_expires = settings.JWT_REFRESH_EXPIRATION_DAYS * 86400
        await store_refresh_token(
            user_id=str(user.id),
            jti=refresh_payload["jti"],
            expires_in_seconds=refresh_expires,
        )

        return user, access_token, refresh_token

    @staticmethod
    async def _issue_tokens(user: User) -> tuple[str, str]:
        """Bir kullanıcı için access+refresh token üret ve refresh'i Redis'e yaz.

        register/login/guest akışlarının ortak token adımı.
        """
        access_token = create_access_token(user_id=str(user.id))
        refresh_token = create_refresh_token(user_id=str(user.id))

        refresh_payload = decode_token(refresh_token, expected_type="refresh")
        refresh_expires = settings.JWT_REFRESH_EXPIRATION_DAYS * 86400
        await store_refresh_token(
            user_id=str(user.id),
            jti=refresh_payload["jti"],
            expires_in_seconds=refresh_expires,
        )
        return access_token, refresh_token

    @staticmethod
    async def guest_login(db: AsyncSession, device_id: str) -> tuple[User, str, str]:
        """Misafir girişi: device_id'ye bağlı hesap varsa onu döndür, yoksa oluştur.

        Şifresiz, cihaz kimliğine bağlı hesap. Username otomatik üretilir
        ("Oyuncu" + kısa rastgele ek) ve çakışmaya karşı yeniden denenir.

        Raises:
            ValueError: device_id boşsa ya da benzersiz username üretilemezse.
            PermissionError: Hesap askıya alınmışsa.
        """
        device_id = (device_id or "").strip()
        if not device_id:
            raise ValueError("Geçersiz cihaz kimliği.")

        result = await db.execute(
            select(User).where(
                User.device_id == device_id,
                User.deleted_at.is_(None),
            )
        )
        user = result.scalar_one_or_none()

        if user is not None:
            if user.is_banned:
                raise PermissionError("Bu hesap askıya alınmış.")
            user.last_login_at = datetime.now(timezone.utc)
        else:
            # Çakışmaya dayanıklı otomatik username: "Oyuncu" + kısa hex ek.
            username = None
            for _ in range(10):
                candidate = f"Oyuncu{secrets.token_hex(3)}"  # ör. Oyuncu3fa9c1
                exists = await db.execute(
                    select(User.id).where(User.username == candidate)
                )
                if exists.scalar_one_or_none() is None:
                    username = candidate
                    break
            if username is None:
                raise ValueError("Misafir hesabı oluşturulamadı, tekrar deneyin.")

            user = User(
                username=username,
                display_name="Oyuncu",
                device_id=device_id,
                is_guest=True,
                auth_provider="guest",
                last_login_at=datetime.now(timezone.utc),
            )
            db.add(user)
            await db.flush()
            await db.refresh(user)

        access_token, refresh_token = await AuthService._issue_tokens(user)
        return user, access_token, refresh_token

    @staticmethod
    async def claim_guest_account(
        db: AsyncSession,
        user_id: str,
        email: str,
        password: str,
        username: str | None = None,
    ) -> User:
        """Misafir hesabı kalıcılaştır: email+şifre (ve isteğe bağlı username) bağla.

        Başarıda is_guest=False olur; oyuncunun tüm ilerlemesi (XP, coin,
        istatistik) aynı hesapta kalır.

        Raises:
            ValueError: Kullanıcı yok/misafir değil, email veya username çakışıyor.
        """
        result = await db.execute(
            select(User).where(User.id == uuid_mod.UUID(str(user_id)))
        )
        user = result.scalar_one_or_none()
        if not user or user.deleted_at is not None:
            raise ValueError("Kullanıcı bulunamadı.")
        if not user.is_guest:
            raise ValueError("Bu hesap zaten kalıcı.")

        # Email çakışması (başka bir hesapta kayıtlıysa düzgün hata)
        email_check = await db.execute(
            select(User.id).where(User.email == email, User.id != user.id)
        )
        if email_check.scalar_one_or_none():
            raise ValueError("Bu e-posta adresi zaten kayıtlı.")

        # İsteğe bağlı yeni username (çakışma kontrolü ile)
        if username and username != user.username:
            name_check = await db.execute(
                select(User.id).where(User.username == username)
            )
            if name_check.scalar_one_or_none():
                raise ValueError("Bu kullanıcı adı zaten alınmış.")
            user.username = username

        user.email = email
        user.password_hash = hash_password(password)
        user.is_guest = False
        user.auth_provider = "email"

        await db.flush()
        await db.refresh(user)
        return user

    @staticmethod
    async def login(
        db: AsyncSession,
        username_or_email: str,
        password: str,
    ) -> tuple[User, str, str]:
        """Login with username/email and password. Returns (user, access_token, refresh_token)."""
        result = await db.execute(
            select(User).where(
                or_(
                    User.username == username_or_email,
                    User.email == username_or_email,
                )
            )
        )
        user = result.scalar_one_or_none()

        if not user or not verify_password(password, user.password_hash):
            raise ValueError("Kullanıcı adı veya şifre hatalı.")

        if user.is_banned:
            raise PermissionError("Bu hesap askıya alınmış.")

        # Update last login
        user.last_login_at = datetime.now(timezone.utc)

        # Generate tokens
        access_token = create_access_token(user_id=str(user.id))
        refresh_token = create_refresh_token(user_id=str(user.id))

        # Store refresh token
        refresh_payload = decode_token(refresh_token, expected_type="refresh")
        refresh_expires = settings.JWT_REFRESH_EXPIRATION_DAYS * 86400
        await store_refresh_token(
            user_id=str(user.id),
            jti=refresh_payload["jti"],
            expires_in_seconds=refresh_expires,
        )

        return user, access_token, refresh_token

    @staticmethod
    async def refresh_access_token(refresh_token_str: str) -> tuple[str, str]:
        """Refresh the access token using a valid refresh token.
        Returns (new_access_token, new_refresh_token).
        Implements refresh token rotation.
        """
        payload = decode_token(refresh_token_str, expected_type="refresh")
        user_id = payload.get("sub")
        jti = payload.get("jti")

        if not user_id or not jti:
            raise ValueError("Geçersiz refresh token.")

        # Check if refresh token is still valid in Redis
        if not await is_refresh_token_valid(jti):
            raise ValueError("Refresh token iptal edilmiş veya süresi dolmuş.")

        # Revoke old refresh token (rotation)
        await revoke_refresh_token(jti)

        # Create new tokens
        new_access_token = create_access_token(user_id=user_id)
        new_refresh_token = create_refresh_token(user_id=user_id)

        # Store new refresh token
        new_payload = decode_token(new_refresh_token, expected_type="refresh")
        refresh_expires = settings.JWT_REFRESH_EXPIRATION_DAYS * 86400
        await store_refresh_token(
            user_id=user_id,
            jti=new_payload["jti"],
            expires_in_seconds=refresh_expires,
        )

        return new_access_token, new_refresh_token

    @staticmethod
    async def logout(user_id: str, access_token_jti: str) -> None:
        """Logout user: blacklist current access token, revoke all refresh tokens."""
        from app.utils.security import blacklist_token

        # Blacklist the access token until it expires
        access_expires = settings.JWT_ACCESS_EXPIRATION_MINUTES * 60
        await blacklist_token(access_token_jti, access_expires)

        # Revoke all refresh tokens
        await revoke_all_refresh_tokens(user_id)

    @staticmethod
    async def change_password(
        db: AsyncSession,
        user_id: str,
        current_password: str,
        new_password: str,
    ) -> None:
        """Change password for authenticated user."""
        result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        if not verify_password(current_password, user.password_hash):
            raise ValueError("Mevcut şifre hatalı.")

        user.password_hash = hash_password(new_password)
        await db.flush()

        # Revoke all existing refresh tokens (security)
        await revoke_all_refresh_tokens(user_id)

    @staticmethod
    async def request_password_reset(db: AsyncSession, email: str) -> str | None:
        """Generate password reset token for user with given email.
        Returns token if email exists, None otherwise (don't leak email existence).
        """
        result = await db.execute(select(User).where(User.email == email))
        user = result.scalar_one_or_none()

        if not user:
            return None  # Don't reveal if email exists

        return create_password_reset_token(user_id=str(user.id))

    @staticmethod
    async def confirm_password_reset(
        db: AsyncSession,
        token: str,
        new_password: str,
    ) -> None:
        """Reset password using a valid reset token."""
        payload = decode_token(token, expected_type="password_reset")
        user_id = payload.get("sub")

        if not user_id:
            raise ValueError("Geçersiz sıfırlama tokeni.")

        result = await db.execute(select(User).where(User.id == uuid_mod.UUID(user_id)))
        user = result.scalar_one_or_none()

        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        user.password_hash = hash_password(new_password)
        await db.flush()

        # Revoke all refresh tokens
        await revoke_all_refresh_tokens(user_id)
