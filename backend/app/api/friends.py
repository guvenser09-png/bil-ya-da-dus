"""Arkadaş uçları — listele, istek gönder/kabul/red, ara, çıkar."""

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.friend_service import FriendService
from app.utils.security import get_current_user_id

router = APIRouter()


# --- İstek gövdeleri ---

class FriendActionRequest(BaseModel):
    user_id: str


# --- Uçlar ---

@router.get("")
async def get_friends(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Kabul edilmiş arkadaşlar."""
    friends = await FriendService.list_friends(db, user_id)
    return {"friends": friends}


@router.get("/requests")
async def get_requests(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Bekleyen istekler: gelen + giden."""
    return await FriendService.list_requests(db, user_id)


@router.get("/search")
async def search_friends(
    q: str = Query(..., min_length=1, max_length=50),
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcı adına göre ara (kendisi/banlı/silinmiş hariç). status alanı içerir."""
    users = await FriendService.search(db, user_id, q)
    return {"users": users}


@router.post("/request")
async def send_friend_request(
    body: FriendActionRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Arkadaşlık isteği gönder. Karşı taraf zaten istek attıysa otomatik kabul."""
    try:
        return await FriendService.send_request(db, user_id, body.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/accept")
async def accept_friend_request(
    body: FriendActionRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Gelen bir isteği kabul et."""
    try:
        return await FriendService.accept_request(db, user_id, body.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/reject")
async def reject_friend_request(
    body: FriendActionRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Gelen bir isteği reddet/sil."""
    try:
        return await FriendService.reject_request(db, user_id, body.user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.delete("/{friend_id}")
async def remove_friend(
    friend_id: str,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Arkadaşlıktan çıkar."""
    try:
        return await FriendService.remove_friend(db, user_id, friend_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc
