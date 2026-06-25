"""Karakter (avatar) ekonomisi — TEK para birimi ALTIN ile bireysel satın alma.

TASARIM (kullanıcı isteği):
  - Karakterler artık "paket" değil; HER karakterin kendi ALTIN fiyatı var.
  - Fiyatlar git gide artar (free → common → rare → epic → legendary). En pahalı
    karakter bir "flex"tir: oyuncu onu kuşandığında lobi/maçta herkes görür
    (avatar_id zaten tüm oyunculara yansıyor) → prestij.
  - Gerçek para YOK; karakterler yalnızca oyun-içi altınla alınır. (Altının
    kendisi mağazadan gerçek parayla da alınabilir; yani "parası olan güzel
    karakteri alır" ama oyun tamamen altın üstüne kuruludur.)

SAHİPLİK: Mevcut `Entitlement` tablosu yeniden kullanılır (DB migration GEREKMEZ):
  item_type = EntitlementType.CHARACTER_PACK, item_id = karakter id'si (örn 'dragon').
  Ücretsiz başlangıç karakterleri (robot/alien/ghost) herkeste her zaman açıktır.

KAYNAK BÜTÜNLÜĞÜ: Fiyatlar BACKEND'de sabittir; istemci fiyat göndermez.
Karakter id'leri mobildeki `mobile/lib/shared/characters.dart` ile birebir aynıdır.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.purchase import Entitlement, EntitlementType
from app.services.user_service import UserService

# --- Karakter kataloğu (id → fiyat/altın, nadirlik) -------------------------
# Sıra ÖNEMLİ: mağaza bu sırayla (ucuzdan pahalıya) gösterir.
# rarity: free | common | rare | epic | legendary  (mobil rozet/renk için)
CHARACTER_CATALOG: list[dict] = [
    # --- Ücretsiz başlangıç (herkeste açık) ---
    {"id": "robot", "name": "Robot", "price_coins": 0, "rarity": "free"},
    {"id": "alien", "name": "Uzaylı", "price_coins": 0, "rarity": "free"},
    {"id": "ghost", "name": "Hayalet", "price_coins": 0, "rarity": "free"},

    # --- Common (hayvanlar) ---
    {"id": "cat_face", "name": "Kedi", "price_coins": 250, "rarity": "common"},
    {"id": "dog_face", "name": "Köpek", "price_coins": 300, "rarity": "common"},
    {"id": "frog", "name": "Kurbağa", "price_coins": 400, "rarity": "common"},
    {"id": "penguin", "name": "Penguen", "price_coins": 500, "rarity": "common"},
    {"id": "fox", "name": "Tilki", "price_coins": 650, "rarity": "common"},
    {"id": "panda", "name": "Panda", "price_coins": 800, "rarity": "common"},
    {"id": "lion", "name": "Aslan", "price_coins": 1000, "rarity": "common"},
    {"id": "tiger", "name": "Kaplan", "price_coins": 1200, "rarity": "common"},

    # --- Rare (uzaylılar) ---
    {"id": "flying_saucer", "name": "UFO", "price_coins": 1600, "rarity": "rare"},
    {"id": "rocket", "name": "Roket", "price_coins": 2000, "rarity": "rare"},
    {"id": "octopus", "name": "Ahtapot", "price_coins": 2600, "rarity": "rare"},
    {"id": "alien_monster", "name": "Uzay Canavarı", "price_coins": 3200, "rarity": "rare"},
    {"id": "dragon_face", "name": "Ejder Yüzü", "price_coins": 4000, "rarity": "rare"},

    # --- Epic (efsanevi) ---
    {"id": "goblin", "name": "Goblin", "price_coins": 5000, "rarity": "epic"},
    {"id": "ogre", "name": "Dev", "price_coins": 6500, "rarity": "epic"},
    {"id": "owl", "name": "Baykuş", "price_coins": 8000, "rarity": "epic"},
    {"id": "unicorn", "name": "Tek Boynuz", "price_coins": 11000, "rarity": "epic"},
    {"id": "dragon", "name": "Ejderha", "price_coins": 15000, "rarity": "epic"},

    # --- Legendary (havalı / prestij) ---
    {"id": "nerd_face", "name": "İnek", "price_coins": 20000, "rarity": "legendary"},
    {"id": "smiling_face_with_sunglasses", "name": "Gözlüklü", "price_coins": 28000, "rarity": "legendary"},
    {"id": "cowboy_hat_face", "name": "Kovboy", "price_coins": 38000, "rarity": "legendary"},
    {"id": "clown_face", "name": "Palyaço", "price_coins": 50000, "rarity": "legendary"},
    {"id": "star-struck", "name": "Yıldız Gözlü", "price_coins": 75000, "rarity": "legendary"},
]

CHARACTER_BY_ID: dict[str, dict] = {c["id"]: c for c in CHARACTER_CATALOG}
FREE_CHARACTER_IDS: set[str] = {c["id"] for c in CHARACTER_CATALOG if c["price_coins"] == 0}
DEFAULT_CHARACTER_ID = "robot"


class CharacterService:
    """Karakter kataloğu, sahiplik, altınla satın alma ve kuşanma kapısı."""

    # ------------------------------------------------------------------
    @staticmethod
    def exists(character_id: str) -> bool:
        return character_id in CHARACTER_BY_ID

    @staticmethod
    def is_free(character_id: str) -> bool:
        return character_id in FREE_CHARACTER_IDS

    @staticmethod
    def price_of(character_id: str) -> int:
        item = CHARACTER_BY_ID.get(character_id)
        return int(item["price_coins"]) if item else 0

    # ------------------------------------------------------------------
    @staticmethod
    async def owned_ids(db: AsyncSession, user_id: str) -> set[str]:
        """Kullanıcının sahip olduğu karakter id'leri (ücretsizler DAHİL)."""
        result = await db.execute(
            select(Entitlement.item_id).where(
                Entitlement.user_id == user_id,
                Entitlement.item_type == EntitlementType.CHARACTER_PACK,
            )
        )
        owned = {row[0] for row in result.all() if row[0] in CHARACTER_BY_ID}
        return owned | FREE_CHARACTER_IDS

    @staticmethod
    async def can_equip(db: AsyncSession, user_id: str, character_id: str) -> bool:
        """Kullanıcı bu karakteri kuşanabilir mi? (ücretsiz veya sahip)."""
        if not CharacterService.exists(character_id):
            return False
        if CharacterService.is_free(character_id):
            return True
        owned = await CharacterService.owned_ids(db, user_id)
        return character_id in owned

    # ------------------------------------------------------------------
    @staticmethod
    async def list_for_user(db: AsyncSession, user_id: str) -> dict:
        """GET /api/store/characters — katalog + sahiplik + kuşanılı + bakiye."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        owned = await CharacterService.owned_ids(db, user_id)
        equipped = user.avatar_id

        items = [
            {
                "id": c["id"],
                "name": c["name"],
                "price_coins": c["price_coins"],
                "rarity": c["rarity"],
                "free": c["price_coins"] == 0,
                "owned": c["id"] in owned,
                "equipped": c["id"] == equipped,
            }
            for c in CHARACTER_CATALOG
        ]
        return {"coins": user.coins or 0, "equipped": equipped, "characters": items}

    # ------------------------------------------------------------------
    @staticmethod
    async def buy(db: AsyncSession, user_id: str, character_id: str) -> dict:
        """POST /api/store/characters/buy — altınla karakter satın al.

        Raises:
            ValueError: geçersiz karakter / zaten sahip / yetersiz altın.
        """
        if not CharacterService.exists(character_id):
            raise ValueError("Geçersiz karakter.")
        if CharacterService.is_free(character_id):
            raise ValueError("Bu karakter zaten ücretsiz.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        owned = await CharacterService.owned_ids(db, user_id)
        if character_id in owned:
            # Idempotent: zaten sahip → ücret düşme, mevcut durumu döndür.
            return {
                "bought": False,
                "already_owned": True,
                "character_id": character_id,
                "coins": user.coins or 0,
            }

        price = CharacterService.price_of(character_id)
        if (user.coins or 0) < price:
            raise ValueError("Yetersiz altın.")

        user.coins = (user.coins or 0) - price
        db.add(
            Entitlement(
                user_id=user.id,
                item_type=EntitlementType.CHARACTER_PACK,
                item_id=character_id,
            )
        )
        await db.flush()

        return {
            "bought": True,
            "already_owned": False,
            "character_id": character_id,
            "coins": user.coins or 0,
        }
