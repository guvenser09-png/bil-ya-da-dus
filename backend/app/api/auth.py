"""Authentication endpoints — register, login, refresh."""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserRegisterRequest, UserLoginRequest, TokenResponse, UserMeResponse
from app.utils.security import hash_password, verify_password, create_access_token

router = APIRouter()


@router.post("/register", response_model=TokenResponse, status_code=status.HTTP_201_CREATED)
async def register(request: UserRegisterRequest, db: AsyncSession = Depends(get_db)):
    """Register a new player account."""
    # Check if username already exists
    result = await db.execute(
        select(User).where(User.username == request.username)
    )
    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Bu kullanıcı adı zaten alınmış.",
        )

    # Check if email already exists
    if request.email:
        result = await db.execute(
            select(User).where(User.email == request.email)
        )
        if result.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT,
                detail="Bu e-posta adresi zaten kayıtlı.",
            )

    # Create user
    user = User(
        username=request.username,
        email=request.email,
        phone=request.phone,
        password_hash=hash_password(request.password),
        display_name=request.display_name or request.username,
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)

    # Generate JWT
    token = create_access_token(user_id=str(user.id))

    return TokenResponse(
        access_token=token,
        user=UserMeResponse.model_validate(user),
    )


@router.post("/login", response_model=TokenResponse)
async def login(request: UserLoginRequest, db: AsyncSession = Depends(get_db)):
    """Login with username/email and password."""
    # Find user by username or email
    result = await db.execute(
        select(User).where(
            (User.username == request.username_or_email)
            | (User.email == request.username_or_email)
        )
    )
    user = result.scalar_one_or_none()

    if not user or not verify_password(request.password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Kullanıcı adı veya şifre hatalı.",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Bu hesap askıya alınmış.",
        )

    # Update last login
    from datetime import datetime, timezone
    user.last_login_at = datetime.now(timezone.utc)

    # Generate JWT
    token = create_access_token(user_id=str(user.id))

    return TokenResponse(
        access_token=token,
        user=UserMeResponse.model_validate(user),
    )
