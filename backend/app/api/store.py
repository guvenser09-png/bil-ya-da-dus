"""Mağaza uçları — katalog, envanter, satın alma, restore.

Koordinatör bu router'ı /store prefix ile bağlayacak (bkz. dosya sonu wiring notu).
"""

from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.security import HTTPBearer
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.services.character_service import CharacterService
from app.services.featured_service import FeaturedService
from app.services.store_service import StoreService
from app.utils.security import decode_token, get_current_user_id

router = APIRouter()

# Auth'un opsiyonel olduğu uçlar için (katalog) — token yoksa hata vermez.
_optional_bearer = HTTPBearer(auto_error=False)


async def get_optional_user_id(
    credentials=Depends(_optional_bearer),
) -> str | None:
    """Token varsa kullanıcı id'sini döndür; yoksa None (hata fırlatmadan)."""
    if credentials is None:
        return None
    try:
        payload = decode_token(credentials.credentials, expected_type="access")
        return payload.get("sub")
    except Exception:
        return None


# --- İstek/yanıt şemaları ---

class PurchaseRequest(BaseModel):
    platform: str  # 'ios' | 'android'
    product_id: str
    # iOS: base64 receipt; Android: purchaseToken. transaction_id opsiyonel.
    receipt: str
    transaction_id: str | None = None


class CharacterBuyRequest(BaseModel):
    character_id: str


# --- Uçlar ---

@router.get("/catalog")
async def get_catalog(
    user_id: str | None = Depends(get_optional_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Ürün kataloğu. Kullanıcı verilirse non-consumable ürünlerde
    `owned` bayrağı işaretlenir."""
    products = await StoreService.get_catalog(db, user_id)
    return {"products": products}


@router.get("/inventory")
async def get_inventory(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının sahip olduğu paketler + premium durumu + altın (coins)."""
    try:
        return await StoreService.get_inventory(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/characters")
async def get_characters(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Karakter kataloğu: her karakterin ALTIN fiyatı + sahiplik + kuşanılı + bakiye.
    Tek para birimi altın; karakterler bireysel olarak altınla alınır."""
    try:
        return await CharacterService.list_for_user(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/characters/buy")
async def buy_character(
    body: CharacterBuyRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Karakteri ALTIN ile satın al. Yetersiz bakiye/geçersiz karakterde 400."""
    try:
        return await CharacterService.buy(db, user_id, body.character_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.get("/starter-pack")
async def get_starter_pack(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Tek seferlik başlangıç paketi uygunluğu (ilk 48 saat).

    `available` True ise istemci /store/purchase ile product_id=starter_pack
    satın alma akışını başlatabilir.
    """
    try:
        return await StoreService.get_starter_pack(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/featured")
async def get_featured(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Haftalık rotasyonlu öne çıkan kozmetikler (indirimli).

    Deterministik: ISO hafta numarasına göre seçilir; aynı hafta herkese aynı.
    İndirimli fiyat satın almada (POST /api/cosmetics/buy) backend'de doğrulanır.
    """
    try:
        return await FeaturedService.get_featured(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.get("/offers")
async def get_offers(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """O an aktif sınırlı süreli teklifler (geri sayımlı).

    Teklifler mevcut katalog ürünlerine bağlıdır; satın alma normal
    POST /api/store/purchase akışını (product_id ile) kullanır.
    """
    try:
        return await FeaturedService.get_offers(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc


@router.post("/purchase")
async def purchase(
    body: PurchaseRequest,
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Makbuzu doğrula ve ürünü ver. transaction_id daha önce işlendiyse
    idempotent başarı döner."""
    try:
        return await StoreService.purchase(
            db,
            user_id=user_id,
            platform=body.platform,
            product_id=body.product_id,
            receipt=body.receipt,
            transaction_id=body.transaction_id,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)
        ) from exc


@router.post("/restore")
async def restore(
    user_id: str = Depends(get_current_user_id),
    db: AsyncSession = Depends(get_db),
):
    """Kullanıcının doğrulanmış non-consumable satın almalarını tekrar uygula."""
    try:
        return await StoreService.restore(db, user_id)
    except ValueError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)
        ) from exc
