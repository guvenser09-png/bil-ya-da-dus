"""Mağaza servisi — ürün kataloğu, satın alma işleme, envanter/restore.

Ürün kataloğu şimdilik sabit liste; ileride DB'ye taşınabilir. Karakter paketi
ID'leri `mobile/lib/shared/characters.dart` ile birebir tutarlıdır:
pack_animals / pack_aliens / pack_mythic / pack_cool. (characters.dart'taki ham
paket id'leri 'animals', 'aliens', ... olduğundan, ürün kimliğinden pack id'ye
çevirim STORE_PACK_TO_CHARACTER_PACK ile yapılır.)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import (
    Entitlement,
    EntitlementType,
    Purchase,
    PurchasePlatform,
    PurchaseStatus,
)
from app.models.cosmetic import UserCosmetic
from app.models.user import User
from app.services.cosmetics_service import CATALOG_BY_ID as COSMETICS_BY_ID
from app.services.iap_verifier import verify_receipt
from app.services.user_service import UserService, _to_uuid

# --- Ürün tipleri ---
PRODUCT_TYPE_COINS = "coins"            # consumable (tek oyun-içi para birimi: altın)
PRODUCT_TYPE_CHARACTER_PACK = "character_pack"  # non-consumable
PRODUCT_TYPE_PREMIUM = "premium"        # abonelik
PRODUCT_TYPE_BATTLE_PASS = "battle_pass"  # sezona özel premium pass (IAP yolu)
PRODUCT_TYPE_STARTER_PACK = "starter_pack"  # tek seferlik açılış paketi

# Premium abonelik süresi (gün).
PREMIUM_DURATION_DAYS = 30
PREMIUM_YEARLY_DAYS = 365

# Starter pack penceresi (saat) — hesap oluşturulduktan sonra.
STARTER_PACK_WINDOW_HOURS = 48
# Starter pack'in eksklüzif çerçeve kozmetiği (cosmetics kataloğunda mevcut).
STARTER_PACK_FRAME_COSMETIC = "frame_royal"


# --- Ürün kataloğu (sabit) ---
# grants: ürün verildiğinde ne sağlanacağı.
#   coins  -> {"coins": int}
#   pack   -> {"character_pack": "<characters.dart pack id>"}
#   premium-> {"premium_days": int, "bonus_coins": int}
CATALOG: list[dict] = [
    # --- Altın paketleri (consumable, gerçek para) ---
    # TEK temiz altın seti. Eski coins_500/1200/2500 paketleri kaldırıldı
    # (mükerrer "500 altın" görünümüne yol açıyordu). Tek oyun-içi para birimi
    # altın; pay-to-win YOK (altın yalnızca karakter/kozmetik/turnuva girişi).
    {
        "product_id": "gold_small",
        "type": PRODUCT_TYPE_COINS,
        "title": "4.000 Altın",
        "description": "Küçük altın paketi",
        "price_display": "₺29,99",
        "price_usd": "$2,99",
        "ios_product_id": "com.bilyadadus.gold_small",
        "android_product_id": "gold_small",
        "grants": {"coins": 4000},
    },
    {
        "product_id": "gold_medium",
        "type": PRODUCT_TYPE_COINS,
        "title": "9.000 Altın (+%12 bonus)",
        "description": "Popüler altın paketi (+%12 bonus)",
        "price_display": "₺59,99",
        "price_usd": "$5,99",
        "bonus_label": "+%12 bonus",
        "ios_product_id": "com.bilyadadus.gold_medium",
        "android_product_id": "gold_medium",
        "grants": {"coins": 9000},
    },
    {
        "product_id": "gold_large",
        "type": PRODUCT_TYPE_COINS,
        "title": "20.000 Altın (+%25 bonus)",
        "description": "Avantajlı altın paketi (+%25 bonus)",
        "price_display": "₺119,99",
        "price_usd": "$11,99",
        "bonus_label": "+%25 bonus",
        "ios_product_id": "com.bilyadadus.gold_large",
        "android_product_id": "gold_large",
        "grants": {"coins": 20000},
    },
    {
        "product_id": "gold_mega",
        "type": PRODUCT_TYPE_COINS,
        "title": "90.000 Altın (+%40 bonus)",
        "description": "En büyük altın paketi (+%40 bonus)",
        "price_display": "₺499,99",
        "price_usd": "$49,99",
        "bonus_label": "+%40 bonus",
        "ios_product_id": "com.bilyadadus.gold_mega",
        "android_product_id": "gold_mega",
        "grants": {"coins": 90000},
    },
    # NOT: Karakter "paketleri" KALDIRILDI. Karakterler artık bireysel olarak
    # ALTIN ile alınır (bkz. character_service.py + /api/store/characters).
    # Battle Pass ve Starter Pack de kaldırıldı (mağaza sadeleştirildi).
    # --- Premium abonelik ---
    # Premium avantajları (pay-to-win YOK, hepsi konfor/kozmetik/yumuşak para):
    #   - Günlük ödüle bonus altın (daily_service)
    #   - 2x sezon puanı (season puanı kazanımında)
    #   - Premium çerçeve kozmetiği
    # NOT: Uygulamada reklam YOK; "reklamsız" ibaresi kullanılmaz (yanıltıcı olur).
    {
        "product_id": "premium_monthly",
        "type": PRODUCT_TYPE_PREMIUM,
        "title": "Premium (Aylık)",
        "description": (
            "Her gün +100 altın + 2x sezon puanı + premium çerçeve"
        ),
        "price_display": "₺79,99",
        "price_usd": "$4,99",
        "ios_product_id": "com.bilyadadus.premium_monthly",
        "android_product_id": "premium_monthly",
        "grants": {
            "premium_days": PREMIUM_DURATION_DAYS,
            "bonus_coins": 300,
            "frame_cosmetic": "frame_neon",
        },
    },
    {
        "product_id": "premium_yearly",
        "type": PRODUCT_TYPE_PREMIUM,
        "title": "Premium (Yıllık)",
        "description": (
            "Yıllık premium — en avantajlı. Her gün +100 altın + "
            "2x sezon puanı + premium çerçeve"
        ),
        "price_display": "₺199,99",
        "price_usd": "$39,99",
        "bonus_label": "En avantajlı",
        "ios_product_id": "com.bilyadadus.premium_yearly",
        "android_product_id": "premium_yearly",
        "grants": {
            "premium_days": PREMIUM_YEARLY_DAYS,
            "bonus_coins": 1000,
            "frame_cosmetic": "frame_neon",
        },
    },
]

# product_id -> ürün dict hızlı erişim.
_CATALOG_BY_ID: dict[str, dict] = {p["product_id"]: p for p in CATALOG}


def get_product(product_id: str) -> dict | None:
    """Katalogdan ürünü getir."""
    return _CATALOG_BY_ID.get(product_id)


class StoreService:
    """Mağaza iş mantığı: katalog, satın alma, envanter, restore."""

    # --- Katalog ---
    @staticmethod
    async def get_catalog(
        db: AsyncSession, user_id: str | None = None
    ) -> list[dict]:
        """Ürün kataloğunu döndür. Kullanıcı verilirse non-consumable
        ürünlerde `owned` bayrağını işaretle."""
        owned_pack_ids: set[str] = set()
        is_premium = False
        if user_id:
            owned_pack_ids = await StoreService._owned_character_packs(db, user_id)
            user = await UserService.get_user_by_id(db, user_id)
            is_premium = bool(user and user.is_premium)

        catalog: list[dict] = []
        for product in CATALOG:
            entry = dict(product)
            if product["type"] == PRODUCT_TYPE_CHARACTER_PACK:
                pack = product["grants"]["character_pack"]
                entry["owned"] = pack in owned_pack_ids
            elif product["type"] == PRODUCT_TYPE_PREMIUM:
                entry["owned"] = is_premium
            else:
                entry["owned"] = False  # consumable (coins/battle_pass/starter)
            catalog.append(entry)
        return catalog

    # --- Starter Pack ---
    @staticmethod
    def _starter_pack_in_window(user) -> bool:
        """Kullanıcı hesabı starter pack penceresinde (ilk 48 saat) mi?"""
        if not user.created_at:
            return False
        created = user.created_at
        if created.tzinfo is None:
            created = created.replace(tzinfo=timezone.utc)
        deadline = created + timedelta(hours=STARTER_PACK_WINDOW_HOURS)
        return datetime.now(timezone.utc) < deadline

    @staticmethod
    async def get_starter_pack(db: AsyncSession, user_id: str) -> dict:
        """GET /api/store/starter-pack — kullanıcı için uygunluk + içerik.

        available True ise istemci satın alma akışını (product_id=starter_pack)
        başlatabilir.
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        product = get_product("starter_pack")
        in_window = StoreService._starter_pack_in_window(user)
        available = bool(
            product and not user.starter_pack_purchased and in_window
        )

        expires_at = None
        if user.created_at:
            created = user.created_at
            if created.tzinfo is None:
                created = created.replace(tzinfo=timezone.utc)
            expires_at = (
                created + timedelta(hours=STARTER_PACK_WINDOW_HOURS)
            ).isoformat()

        return {
            "available": available,
            "already_purchased": bool(user.starter_pack_purchased),
            "expires_at": expires_at,
            "product_id": "starter_pack",
            "price_display": product["price_display"] if product else None,
            "price_usd": product.get("price_usd") if product else None,
            "contents": {
                "coins": product["grants"].get("coins", 0) if product else 0,
                "premium_days": product["grants"].get("premium_days", 0) if product else 0,
                "frame_cosmetic": product["grants"].get("frame_cosmetic") if product else None,
            },
        }

    # --- Envanter ---
    @staticmethod
    async def get_inventory(db: AsyncSession, user_id: str) -> dict:
        """Kullanıcının sahip olduğu paketler + premium + para birimleri."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        # Artık bireysel karakter id'leri (entitlement item_id) tutulur.
        owned_characters = sorted(await StoreService._owned_character_packs(db, user_id))
        return {
            "coins": user.coins,
            "is_premium": user.is_premium,
            "premium_until": (
                user.premium_until.isoformat() if user.premium_until else None
            ),
            "starter_pack_purchased": bool(user.starter_pack_purchased),
            "characters": owned_characters,
        }

    @staticmethod
    async def _owned_character_packs(db: AsyncSession, user_id: str) -> set[str]:
        """Kullanıcının sahip olduğu karakter paketi id'leri (characters.dart id'si)."""
        result = await db.execute(
            select(Entitlement.item_id).where(
                Entitlement.user_id == _to_uuid(user_id),
                Entitlement.item_type == EntitlementType.CHARACTER_PACK,
            )
        )
        return {row[0] for row in result.all()}

    # --- Satın alma ---
    @staticmethod
    async def purchase(
        db: AsyncSession,
        user_id: str,
        platform: str,
        product_id: str,
        receipt: str,
        transaction_id: str | None = None,
    ) -> dict:
        """Makbuzu doğrula, idempotent şekilde ürünü ver.

        Raises:
            ValueError: Geçersiz ürün/platform veya doğrulama başarısız.
        """
        product = get_product(product_id)
        if not product:
            raise ValueError(f"Geçersiz ürün: {product_id}")

        platform_norm = (platform or "").lower()
        if platform_norm not in ("ios", "android"):
            raise ValueError(f"Geçersiz platform: {platform}")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        # --- Ürün-özel ön koşullar (idempotent / tek seferlik kontrolleri) ---
        if product["type"] == PRODUCT_TYPE_STARTER_PACK:
            if user.starter_pack_purchased:
                raise ValueError("Başlangıç paketini zaten aldınız.")
            if not StoreService._starter_pack_in_window(user):
                raise ValueError("Başlangıç paketi süresi doldu (ilk 48 saat).")
        elif product["type"] == PRODUCT_TYPE_BATTLE_PASS:
            if user.has_battle_pass:
                raise ValueError("Battle Pass'e zaten sahipsiniz.")

        # Makbuzu doğrula. Mağaza tarafındaki gerçek ürün kimliklerini
        # (com.bilyadadus.*) makbuz eşleştirmesi için geçir; bizim katalog
        # product_id'miz (örn premium_monthly) sonuçta döner.
        result = await verify_receipt(
            platform_norm,
            receipt,
            product_id,
            transaction_id,
            apple_product_id=product.get("ios_product_id"),
            google_product_id=product.get("android_product_id"),
        )
        if not result.ok or not result.transaction_id:
            # Başarısızlık kaydını best-effort yaz (txn varsa).
            raise ValueError(result.reason or "Makbuz doğrulanamadı.")

        txn_id = result.transaction_id

        # Idempotency: bu transaction_id daha önce işlendiyse tekrar verme.
        existing = await db.execute(
            select(Purchase).where(Purchase.transaction_id == txn_id)
        )
        prior = existing.scalar_one_or_none()
        if prior is not None:
            return {
                "status": "already_processed",
                "product_id": product_id,
                "transaction_id": txn_id,
                "inventory": await StoreService.get_inventory(db, user_id),
            }

        # Purchase kaydı oluştur.
        purchase = Purchase(
            user_id=user.id,
            platform=PurchasePlatform(platform_norm),
            product_id=product_id,
            transaction_id=txn_id,
            status=PurchaseStatus.VERIFIED,
            amount=result.amount,
            currency=result.currency,
        )
        db.add(purchase)

        # Ürünü ver. Abonelikse, Apple/Google'ın bildirdiği gerçek bitiş
        # tarihini (varsa) premium_until için kullan.
        await StoreService._grant_product(
            db, user, product, verify_expires=result.expires_at
        )

        await db.flush()

        return {
            "status": "verified",
            "product_id": product_id,
            "transaction_id": txn_id,
            "inventory": await StoreService.get_inventory(db, user_id),
        }

    @staticmethod
    async def _grant_product(
        db: AsyncSession,
        user: User,
        product: dict,
        verify_expires: datetime | None = None,
    ) -> None:
        """Ürün tipine göre kullanıcıya hak ver. (flush çağrılmaz; çağıran yapar.)

        verify_expires: Abonelikler için mağazanın bildirdiği gerçek bitiş
            tarihi (Apple expires_date / Google expiryTimeMillis). Verilirse
            premium_until bu değere set edilir (kataloğun sabit gün sayısı yerine).
        """
        grants = product.get("grants", {})
        ptype = product["type"]

        if ptype == PRODUCT_TYPE_COINS:
            user.coins = (user.coins or 0) + int(grants.get("coins", 0))

        elif ptype == PRODUCT_TYPE_CHARACTER_PACK:
            pack_id = grants["character_pack"]
            await StoreService._ensure_entitlement(
                db, user, EntitlementType.CHARACTER_PACK, pack_id
            )

        elif ptype == PRODUCT_TYPE_PREMIUM:
            await StoreService._grant_premium(
                db, user, grants, product["product_id"], verify_expires
            )

        elif ptype == PRODUCT_TYPE_BATTLE_PASS:
            # Premium sezon hattını aç (IAP). Pay-to-win YOK.
            user.has_battle_pass = True

        elif ptype == PRODUCT_TYPE_STARTER_PACK:
            # Tek seferlik açılış paketi: altın + kısa premium + eksklüzif çerçeve.
            user.coins = (user.coins or 0) + int(grants.get("coins", 0))
            premium_days = int(grants.get("premium_days", 0))
            if premium_days > 0:
                await StoreService._grant_premium(
                    db, user, {"premium_days": premium_days}, product["product_id"]
                )
            await StoreService._grant_frame_cosmetic(
                db, user, grants.get("frame_cosmetic")
            )
            user.starter_pack_purchased = True

    @staticmethod
    async def _grant_premium(
        db: AsyncSession,
        user: User,
        grants: dict,
        product_id: str,
        verify_expires: datetime | None = None,
    ) -> None:
        """Premium süresini uzat + bonus coin + premium çerçeve ver.

        verify_expires verilirse (mağazanın bildirdiği gerçek abonelik bitişi),
        premium_until bu değere set edilir — mağaza otoritedir. Aksi halde
        kataloğun sabit gün sayısı eklenir (yenileme mantığıyla).
        """
        now = datetime.now(timezone.utc)
        user.is_premium = True
        if verify_expires is not None:
            if verify_expires.tzinfo is None:
                verify_expires = verify_expires.replace(tzinfo=timezone.utc)
            # Mevcut premium daha ileri bir tarihteyse onu koru.
            current = user.premium_until
            if current is not None and current.tzinfo is None:
                current = current.replace(tzinfo=timezone.utc)
            user.premium_until = (
                max(current, verify_expires) if current else verify_expires
            )
        else:
            days = int(grants.get("premium_days", PREMIUM_DURATION_DAYS))
            base = (
                user.premium_until
                if user.premium_until and user.premium_until > now
                else now
            )
            user.premium_until = base + timedelta(days=days)
        user.coins = (user.coins or 0) + int(grants.get("bonus_coins", 0))
        await StoreService._grant_frame_cosmetic(db, user, grants.get("frame_cosmetic"))
        await StoreService._ensure_entitlement(
            db, user, EntitlementType.PREMIUM, product_id
        )

    @staticmethod
    async def _grant_frame_cosmetic(
        db: AsyncSession, user: User, cosmetic_id: str | None
    ) -> None:
        """Bir çerçeve kozmetiğini idempotent şekilde kullanıcıya ekle."""
        if not cosmetic_id or cosmetic_id not in COSMETICS_BY_ID:
            return
        existing = await db.execute(
            select(UserCosmetic.id).where(
                UserCosmetic.user_id == user.id,
                UserCosmetic.cosmetic_id == cosmetic_id,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(UserCosmetic(user_id=user.id, cosmetic_id=cosmetic_id))

    @staticmethod
    async def _ensure_entitlement(
        db: AsyncSession,
        user: User,
        item_type: EntitlementType,
        item_id: str,
    ) -> None:
        """Aynı hak yoksa Entitlement ekle (idempotent)."""
        existing = await db.execute(
            select(Entitlement).where(
                Entitlement.user_id == user.id,
                Entitlement.item_type == item_type,
                Entitlement.item_id == item_id,
            )
        )
        if existing.scalar_one_or_none() is None:
            db.add(
                Entitlement(
                    user_id=user.id, item_type=item_type, item_id=item_id
                )
            )

    # --- Restore ---
    @staticmethod
    async def restore(db: AsyncSession, user_id: str) -> dict:
        """Kullanıcının doğrulanmış satın almalarını tekrar uygula.

        Non-consumable (karakter paketi, premium) hakları yeniden verir.
        Consumable (coin) paketleri restore edilmez — zaten kullanılmıştır.
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        result = await db.execute(
            select(Purchase).where(
                Purchase.user_id == user.id,
                Purchase.status == PurchaseStatus.VERIFIED,
            )
        )
        purchases = result.scalars().all()

        restored: list[str] = []
        now = datetime.now(timezone.utc)
        for p in purchases:
            product = get_product(p.product_id)
            if not product:
                continue
            ptype = product["type"]
            if ptype == PRODUCT_TYPE_COINS:
                continue  # consumable, restore edilmez
            grants = product.get("grants", {})
            if ptype == PRODUCT_TYPE_CHARACTER_PACK:
                # Sadece SAHİPLİĞİ geri yükle (idempotent). Coin/ödül verme.
                await StoreService._ensure_entitlement(
                    db, user, EntitlementType.CHARACTER_PACK, grants["character_pack"]
                )
                restored.append(p.product_id)
            elif ptype == PRODUCT_TYPE_PREMIUM:
                # Premium sahipliğini geri yükle; süreyi UZATMA, bonus coin VERME.
                # Yalnızca abonelik HÂLÂ geçerliyse is_premium'u aç (süresi
                # geçmiş aboneliği restore ile yeniden başlatma).
                await StoreService._ensure_entitlement(
                    db, user, EntitlementType.PREMIUM, p.product_id
                )
                if user.premium_until and user.premium_until > now:
                    user.is_premium = True
                restored.append(p.product_id)

        await db.flush()
        return {
            "restored": restored,
            "inventory": await StoreService.get_inventory(db, user_id),
        }
