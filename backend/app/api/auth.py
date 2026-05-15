"""Authentication endpoints — register, login, refresh, logout, password reset."""

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.database import get_db
from app.schemas.user import (
    MessageResponse,
    PasswordChangeRequest,
    PasswordResetConfirm,
    PasswordResetRequest,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserMeResponse,
    UserRegisterRequest,
)
from app.services.auth_service import AuthService
from app.utils.security import decode_token, get_current_user_id

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new player account.

    Creates a new user with the provided credentials and returns
    both access and refresh tokens for immediate authentication.
    """
    try:
        user, access_token, refresh_token = await AuthService.register(
            db=db,
            username=request.username,
            password=request.password,
            email=request.email,
            phone=request.phone,
            display_name=request.display_name,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(e),
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_EXPIRATION_MINUTES * 60,
        user=UserMeResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username/email and password.

    Supports login with either username or email address.
    Returns access and refresh tokens on success.
    """
    try:
        user, access_token, refresh_token = await AuthService.login(
            db=db,
            username_or_email=request.username_or_email,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )
    except PermissionError as e:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=str(e),
        )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.JWT_ACCESS_EXPIRATION_MINUTES * 60,
        user=UserMeResponse.model_validate(user),
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(request: RefreshTokenRequest, db: AsyncSession = Depends(get_db)):
    """Refresh access token using a valid refresh token.

    Implements refresh token rotation: the old refresh token is
    invalidated and a new one is returned alongside the new access token.
    """
    try:
        new_access, new_refresh = await AuthService.refresh_access_token(
            refresh_token_str=request.refresh_token,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    # Get user info for response
    payload = decode_token(new_access, expected_type="access")
    import uuid as uuid_mod
    from sqlalchemy import select
    from app.models.user import User

    result = await db.execute(select(User).where(User.id == uuid_mod.UUID(payload["sub"])))
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı bulunamadı.",
        )

    return TokenResponse(
        access_token=new_access,
        refresh_token=new_refresh,
        expires_in=settings.JWT_ACCESS_EXPIRATION_MINUTES * 60,
        user=UserMeResponse.model_validate(user),
    )


@router.post("/logout", response_model=MessageResponse)
async def logout(
    http_request: Request,
    user_id: str = Depends(get_current_user_id),
):
    """Logout the current user.

    Blacklists the current access token and revokes all refresh tokens.
    The user will need to login again to get new tokens.
    """
    # Get the JTI from the current access token
    auth_header = http_request.headers.get("Authorization", "")
    token = auth_header.replace("Bearer ", "")
    payload = decode_token(token, expected_type="access")
    jti = payload.get("jti", "")

    await AuthService.logout(user_id=user_id, access_token_jti=jti)

    return MessageResponse(message="Başarıyla çıkış yapıldı.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    request: PasswordChangeRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Change password for the authenticated user.

    Requires the current password for verification.
    After password change, all existing refresh tokens are revoked.
    """
    try:
        await AuthService.change_password(
            db=db,
            user_id=user_id,
            current_password=request.current_password,
            new_password=request.new_password,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return MessageResponse(message="Şifre başarıyla değiştirildi.")


@router.post("/password-reset", response_model=MessageResponse)
async def request_password_reset(
    request: PasswordResetRequest,
    db: AsyncSession = Depends(get_db),
):
    """Request a password reset token.

    If the email exists, generates a reset token.
    In production, this token would be sent via email.
    For development, the token is returned in the response.
    """
    token = await AuthService.request_password_reset(db=db, email=request.email)

    if settings.DEBUG and token:
        # In development, return the token directly
        return MessageResponse(
            message=f"Şifre sıfırlama bağlantısı gönderildi. [DEV TOKEN: {token}]"
        )

    # Always return success (don't leak email existence)
    return MessageResponse(
        message="Eğer bu e-posta adresine kayıtlı bir hesap varsa, sıfırlama bağlantısı gönderildi."
    )


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def confirm_password_reset(
    request: PasswordResetConfirm,
    db: AsyncSession = Depends(get_db),
):
    """Confirm password reset with the token received via email.

    Resets the password and revokes all existing sessions.
    """
    try:
        await AuthService.confirm_password_reset(
            db=db,
            token=request.token,
            new_password=request.new_password,
        )
    except (ValueError, HTTPException) as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e) if isinstance(e, ValueError) else e.detail,
        )

    return MessageResponse(message="Şifre başarıyla sıfırlandı. Lütfen yeniden giriş yapın.")
