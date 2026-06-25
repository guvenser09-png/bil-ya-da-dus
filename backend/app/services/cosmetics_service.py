"""Kozmetik katalog + satın alma/kuşanma mantığı.

Kozmetikler yumuşak para (coins) ile alınır — IAP DEĞİLDİR. Katalog kod
tarafında sabit tutulur; sahiplik `UserCosmetic` tablosunda saklanır;
kuşanılmış öğeler `User.equipped_*` alanlarında tutulur.

Slotlar: 'frame' (çerçeve), 'name_color' (isim rengi), 'effect' (efekt).
"""

import hashlib

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic import UserCosmetic
from app.models.user import User
from app.services.user_service import UserService, _to_uuid

# --- Sabit katalog ---
# Her öğe: id, slot, name, price_coins,
#          (name_color için) color_hex, (frame/effect için) style.
CATALOG: list[dict] = [
    # Çerçeveler (frame)
    {"id": "frame_gold", "slot": "frame", "name": "Altın Çerçeve",
     "price_coins": 500, "style": "gold"},
    {"id": "frame_neon", "slot": "frame", "name": "Neon Çerçeve",
     "price_coins": 800, "style": "neon"},
    {"id": "frame_fire", "slot": "frame", "name": "Ateş Çerçeve",
     "price_coins": 1200, "style": "fire"},
    {"id": "frame_ice", "slot": "frame", "name": "Buz Çerçeve",
     "price_coins": 1200, "style": "ice"},
    {"id": "frame_royal", "slot": "frame", "name": "Kraliyet Çerçeve",
     "price_coins": 2000, "style": "royal"},

    # İsim renkleri (name_color)
    {"id": "name_gold", "slot": "name_color", "name": "Altın İsim",
     "price_coins": 400, "color_hex": "#FFD23F"},
    {"id": "name_mint", "slot": "name_color", "name": "Nane İsim",
     "price_coins": 400, "color_hex": "#1DDFBE"},
    {"id": "name_pink", "slot": "name_color", "name": "Pembe İsim",
     "price_coins": 400, "color_hex": "#FF479C"},
    {"id": "name_rainbow", "slot": "name_color", "name": "Gökkuşağı İsim",
     "price_coins": 1500, "color_hex": "rainbow"},

    # Efektler (effect)
    {"id": "fx_confetti", "slot": "effect", "name": "Konfeti Efekti",
     "price_coins": 600, "style": "confetti"},
    {"id": "fx_fireworks", "slot": "effect", "name": "Havai Fişek Efekti",
     "price_coins": 1000, "style": "fireworks"},
    {"id": "fx_hearts", "slot": "effect", "name": "Kalp Efekti",
     "price_coins": 800, "style": "hearts"},

    # --- Eksklüzif TURNUVA ödül kozmetikleri (MAĞAZADAN SATIN ALINAMAZ) ---
    # source="tournament" → sadece sezon sonu top sıralara dağıtılır. price yok.
    # Pay-to-win YOK: bunlar statü/görsel; oyun avantajı vermez.
    {"id": "frame_champion", "slot": "frame", "name": "Şampiyon Çerçevesi",
     "style": "champion", "source": "tournament"},
    {"id": "name_champion", "slot": "name_color", "name": "Şampiyon İsmi",
     "color_hex": "#FF3B6B", "source": "tournament"},
    {"id": "fx_crown", "slot": "effect", "name": "Taç Efekti",
     "style": "crown", "source": "tournament"},
    {"id": "frame_legend", "slot": "frame", "name": "Efsane Çerçevesi",
     "style": "legend", "source": "tournament"},
]

# Hızlı erişim için id -> öğe haritası.
CATALOG_BY_ID: dict[str, dict] = {item["id"]: item for item in CATALOG}

VALID_SLOTS = {"frame", "name_color", "effect"}

# Slot -> User üzerindeki kuşanma alanı.
SLOT_FIELD = {
    "frame": "equipped_frame",
    "name_color": "equipped_name_color",
    "effect": "equipped_effect",
}


class CosmeticsService:
    """Kozmetik katalog listeleme, satın alma ve kuşanma mantığı."""

    @staticmethod
    async def _owned_ids(db: AsyncSession, user_id: str) -> set[str]:
        """Kullanıcının sahip olduğu kozmetik id'lerini döner."""
        result = await db.execute(
            select(UserCosmetic.cosmetic_id).where(
                UserCosmetic.user_id == _to_uuid(user_id)
            )
        )
        return set(result.scalars().all())

    @staticmethod
    def _equipped(user) -> dict:
        """Kullanıcının kuşanılmış kozmetiklerini döner."""
        return {
            "frame": user.equipped_frame,
            "name_color": user.equipped_name_color,
            "effect": user.equipped_effect,
        }

    @staticmethod
    async def list_catalog(db: AsyncSession, user_id: str) -> dict:
        """GET /api/cosmetics yanıtını üretir (owned bayraklarıyla)."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        owned = await CosmeticsService._owned_ids(db, user_id)
        # Mağaza kataloğu: satın alınabilir kozmetikler + kullanıcının SAHİP olduğu
        # eksklüzif turnuva kozmetikleri (kazandıysa görsün/kuşansın). Sahip
        # olmadığı turnuva kozmetikleri mağazada listelenmez (satılmaz).
        catalog = [
            {**item, "owned": item["id"] in owned}
            for item in CATALOG
            if item.get("source") != "tournament" or item["id"] in owned
        ]

        return {
            "catalog": catalog,
            "equipped": CosmeticsService._equipped(user),
            "coins": user.coins or 0,
        }

    @staticmethod
    async def buy(db: AsyncSession, user_id: str, cosmetic_id: str) -> dict:
        """POST /api/cosmetics/buy — coin ile kozmetik satın alır.

        Raises:
            ValueError: Geçersiz id / zaten sahip / yetersiz coin.
        """
        item = CATALOG_BY_ID.get(cosmetic_id)
        if not item:
            raise ValueError("Geçersiz kozmetik kimliği.")

        # Eksklüzif turnuva kozmetikleri mağazadan ALINAMAZ — sadece sezon ödülü.
        if item.get("source") == "tournament":
            raise ValueError("Bu kozmetik yalnızca turnuva ödülü olarak kazanılır.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        owned = await CosmeticsService._owned_ids(db, user_id)
        if cosmetic_id in owned:
            raise ValueError("Bu kozmetiğe zaten sahipsiniz.")

        # İndirim doğrulaması (FOMO): kozmetik bu hafta öne çıkıyorsa indirimli
        # fiyattan satılır. Fiyat istemciden ALINMAZ; backend'de hesaplanır.
        # Süresi geçmiş/indirimde olmayan kozmetik normal fiyata döner.
        from app.services.featured_service import FeaturedService

        price = item["price_coins"]
        discounted = FeaturedService.discounted_price_for(cosmetic_id)
        applied_discount = False
        if discounted is not None and discounted < price:
            price = discounted
            applied_discount = True

        if (user.coins or 0) < price:
            raise ValueError("Yetersiz coin.")

        user.coins = (user.coins or 0) - price
        db.add(
            UserCosmetic(user_id=user.id, cosmetic_id=cosmetic_id)
        )
        await db.flush()
        await db.refresh(user)

        return {
            "owned": True,
            "coins": user.coins,
            "price_paid": price,
            "discount_applied": applied_discount,
        }

    @staticmethod
    async def equip(
        db: AsyncSession, user_id: str, slot: str, cosmetic_id: str | None
    ) -> dict:
        """POST /api/cosmetics/equip — sahip olunan öğeyi slota kuşanır.

        cosmetic_id None ise ilgili slottan çıkarır.

        Raises:
            ValueError: Geçersiz slot / sahip olunmayan öğe / slot uyuşmazlığı.
        """
        if slot not in VALID_SLOTS:
            raise ValueError("Geçersiz slot.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        field = SLOT_FIELD[slot]

        if cosmetic_id is None:
            # Slottan çıkar.
            setattr(user, field, None)
        else:
            item = CATALOG_BY_ID.get(cosmetic_id)
            if not item:
                raise ValueError("Geçersiz kozmetik kimliği.")
            if item["slot"] != slot:
                raise ValueError("Kozmetik bu slota ait değil.")

            owned = await CosmeticsService._owned_ids(db, user_id)
            if cosmetic_id not in owned:
                raise ValueError("Bu kozmetiğe sahip değilsiniz.")

            setattr(user, field, cosmetic_id)

        await db.flush()
        await db.refresh(user)

        return {"equipped": CosmeticsService._equipped(user)}

    # ------------------------------------------------------------------
    # Maç/lobi içi kozmetik görünürlüğü (20 kişilik vitrin)
    # ------------------------------------------------------------------

    @staticmethod
    async def equipped_for_users(
        db: AsyncSession, user_ids: list[str]
    ) -> dict[str, dict]:
        """Birden çok kullanıcının kuşanılmış kozmetiklerini TEK sorguda çeker.

        N+1 önlemek için ``WHERE id IN (...)`` kullanılır. Dönen sözlük
        ``{user_id_str: {"frame": ..., "name_color": ..., "effect": ...}}``
        biçimindedir; alanlar mobilin oyuncu objesinde okuduğu anahtarlarla
        (frame / name_color / effect) hizalıdır. Bulunamayan kullanıcılar
        sözlükte yer almaz (çağıran taraf boş kozmetikle devam eder).
        """
        # Geçersiz / dönüştürülemeyen id'leri ele (bot id'leri vb. zaten gelmez).
        uuids = []
        for uid in user_ids:
            if not uid:
                continue
            try:
                uuids.append(_to_uuid(uid))
            except Exception:
                continue
        if not uuids:
            return {}

        result = await db.execute(
            select(
                User.id,
                User.equipped_frame,
                User.equipped_name_color,
                User.equipped_effect,
            ).where(User.id.in_(uuids))
        )
        out: dict[str, dict] = {}
        for row in result.all():
            out[str(row[0])] = {
                "frame": row[1],
                "name_color": row[2],
                "effect": row[3],
            }
        return out

    # Botlara dağıtılacak ücretsiz/görsel kozmetikler (pay-to-win YOK).
    # Çoğu bot çıplak kalır; bir kısmına deterministik (bot adından türetilen)
    # hafif çeşitlilik verilir ki 20 kişilik maç "canlı vitrin" gibi görünsün.
    _BOT_FRAME_POOL = [None, None, None, "frame_gold", "frame_neon", "frame_ice"]
    _BOT_EFFECT_POOL = [None, None, None, None, "fx_confetti", "fx_hearts"]
    _BOT_NAME_COLOR_POOL = [None, None, None, "name_gold", "name_mint", "name_pink"]

    @staticmethod
    def cosmetics_for_bot(bot_name: str) -> dict:
        """Bir bota DETERMİNİSTİK görsel kozmetik atar (bot adı seed'iyle).

        Aynı bot adı her zaman aynı kozmetiği alır → snapshot/yeniden bağlanma
        tutarlı kalır. Sadece görsel; ücretsiz katalog öğeleri kullanılır.
        Dönen sözlük gerçek oyuncularla aynı anahtarlara sahiptir.
        """
        seed = int(hashlib.md5(bot_name.encode("utf-8")).hexdigest(), 16)
        frame = CosmeticsService._BOT_FRAME_POOL[
            seed % len(CosmeticsService._BOT_FRAME_POOL)
        ]
        effect = CosmeticsService._BOT_EFFECT_POOL[
            (seed // 7) % len(CosmeticsService._BOT_EFFECT_POOL)
        ]
        name_color = CosmeticsService._BOT_NAME_COLOR_POOL[
            (seed // 13) % len(CosmeticsService._BOT_NAME_COLOR_POOL)
        ]
        return {"frame": frame, "name_color": name_color, "effect": effect}
