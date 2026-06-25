"""User profile endpoints — view, update, search, stats."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.schemas.user import (
    MessageResponse,
    UserMeResponse,
    UserPublicResponse,
    UserStatsResponse,
    UserUpdateRequest,
)
from app.services.user_service import UserService
from app.utils.security import get_current_user_id

router = APIRouter()


@router.get("/me", response_model=UserMeResponse)
async def get_my_profile(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get the authenticated user's full profile.

    Returns all profile data including private fields like
    email, phone, currency balance, etc.
    """
    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )
    return UserMeResponse.model_validate(user)


@router.patch("/me", response_model=UserMeResponse)
async def update_my_profile(
    request: UserUpdateRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Update the authenticated user's profile.

    Supports partial updates — only provided fields are changed.
    Bio and display name are checked for profanity.
    Interest tags are limited to 5 items.
    """
    update_data = request.model_dump(exclude_unset=True)

    if not update_data:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Güncellenecek alan belirtilmedi.",
        )

    try:
        user = await UserService.update_profile(
            db=db,
            user_id=user_id,
            **update_data,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )

    return UserMeResponse.model_validate(user)


@router.delete("/me", response_model=MessageResponse)
async def delete_my_account(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Hesabı kalıcı olarak sil (KVKK/GDPR uyumlu soft-delete + anonimleştirme).

    Apple App Store için ZORUNLU. Kişisel veriler (e-posta, telefon, şifre,
    görünen isim, bio vb.) temizlenir/anonimleştirilir, hesap pasifleştirilir
    ve tüm oturumlar sonlandırılır. Silinen hesap tekrar giriş yapamaz.
    """
    try:
        await UserService.delete_account(db=db, user_id=user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )

    return MessageResponse(
        message="Hesabınız ve kişisel verileriniz silindi. Bizi tercih ettiğiniz için teşekkürler."
    )


@router.get("/me/stats", response_model=UserStatsResponse)
async def get_my_stats(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Get detailed statistics for the authenticated user.

    Returns comprehensive game stats including accuracy rate,
    best streak, and total score.
    """
    try:
        stats = await UserService.get_user_stats(db, user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return stats


@router.get("/search", response_model=list[UserPublicResponse])
async def search_users(
    q: str = Query(..., min_length=2, max_length=30, description="Aranacak kullanıcı adı"),
    limit: int = Query(10, ge=1, le=50, description="Sonuç sayısı"),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Search for users by username or display name.

    Returns a list of matching public profiles, excluding
    the searching user and banned accounts.
    """
    users = await UserService.search_users(
        db=db,
        query=q,
        limit=limit,
        exclude_user_id=user_id,
    )
    return [UserPublicResponse.model_validate(u) for u in users]


@router.get("/{target_user_id}", response_model=UserPublicResponse)
async def get_user_profile(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get another player's public profile.

    Returns only publicly visible information (no email, phone, etc.)
    """
    user = await UserService.get_user_by_id(db, target_user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )

    if user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )

    return UserPublicResponse.model_validate(user)


@router.get("/{target_user_id}/stats", response_model=UserStatsResponse)
async def get_user_stats(
    target_user_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Get another player's game statistics.

    Returns public game stats for any active user.
    """
    user = await UserService.get_user_by_id(db, target_user_id)
    if not user or user.is_banned:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Kullanıcı bulunamadı.",
        )

    try:
        stats = await UserService.get_user_stats(db, target_user_id)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e),
        )
    return stats
