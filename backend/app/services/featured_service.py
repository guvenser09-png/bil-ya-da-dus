"""FOMO mekaniği — haftalık rotasyonlu öne çıkan kozmetikler + sınırlı süreli teklif.

Gelir için FOMO (kaçırma korkusu) mekaniği:
  1) HAFTALIK ROTASYONLU MAĞAZA: her hafta kozmetik kataloğundan deterministik
     seçilmiş bir alt küme, indirimli fiyatla öne çıkar. Aynı hafta herkese aynı;
     hafta değişince set yenilenir.
  2) SINIRLI SÜRELİ TEKLİF (LTO): o an aktif, geri sayımlı IAP teklifleri.

İLKE: pay-to-win YOK. Burada yalnızca kozmetik indirimleri ve altın/premium
bundle'ları var; oyun gücü veren hiçbir şey satılmaz.

Determinizm: ISO hafta numarasına göre seed = yıl*53 + hafta. Aynı seed → aynı
seçim. Zaman kaynağı her zaman UTC (`datetime.now(timezone.utc)`).
"""

from __future__ import annotations

import random
from datetime import datetime, timedelta, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.cosmetics_service import (
    CATALOG as COSMETICS_CATALOG,
    CATALOG_BY_ID as COSMETICS_BY_ID,
    CosmeticsService,
)
from app.services.user_service import UserService

# --- Haftalık öne çıkan kozmetik ayarları ---
FEATURED_COUNT = 4          # her hafta öne çıkan kozmetik sayısı
FEATURED_DISCOUNT_PCT = 35  # indirim yüzdesi (%30-40 arası)


# --- Hafta hesabı (deterministik) ---

def _iso_week_seed(now: datetime) -> tuple[int, int, int]:
    """(seed, iso_year, iso_week) döndür. Seed = yıl*53 + hafta (deterministik)."""
    iso_year, iso_week, _ = now.isocalendar()
    seed = iso_year * 53 + iso_week
    return seed, iso_year, iso_week


def _week_id(iso_year: int, iso_week: int) -> str:
    """'2026-W24' biçiminde insan-okunur hafta kimliği."""
    return f"{iso_year}-W{iso_week:02d}"


def _week_end_utc(now: datetime) -> datetime:
    """İçinde bulunulan ISO haftanın sonu (Pazar 23:59:59.999999 UTC)."""
    # ISO haftada Pazartesi=1 ... Pazar=7. Haftanın sonuna kalan gün sayısı.
    weekday = now.isoweekday()  # 1..7
    days_until_sunday = 7 - weekday
    sunday = (now + timedelta(days=days_until_sunday)).date()
    # Pazar gününün son anı (UTC).
    return datetime(
        sunday.year, sunday.month, sunday.day,
        23, 59, 59, 999999, tzinfo=timezone.utc,
    )


def _discounted_price(original: int, discount_pct: int) -> int:
    """İndirimli coin fiyatı (yukarı yuvarlama yok; tam sayıya yuvarla)."""
    return max(1, round(original * (100 - discount_pct) / 100))


def _select_featured_ids(now: datetime) -> list[str]:
    """O haftaya özel deterministik kozmetik id alt kümesi.

    Seed'i sabit olduğundan aynı hafta her çağrıda aynı sırayı/seçimi verir.
    """
    seed, _, _ = _iso_week_seed(now)
    rng = random.Random(seed)
    # Sadece coin ile satılabilen kozmetikler öne çıkabilir. Turnuva-özel
    # ödüller (source="tournament") `price_coins` taşımaz → seçilirlerse
    # /api/store/featured 500 verirdi. Bunları havuzdan dışla.
    all_ids = [
        item["id"] for item in COSMETICS_CATALOG
        if item.get("source") != "tournament" and isinstance(item.get("price_coins"), int)
    ]
    count = min(FEATURED_COUNT, len(all_ids))
    # rng.sample kopya üzerinde çalışır; katalog sırasını bozmaz.
    return rng.sample(all_ids, count)


class FeaturedService:
    """Haftalık öne çıkan kozmetikler ve sınırlı süreli teklifler."""

    # --- Haftalık öne çıkanlar ---
    @staticmethod
    def featured_ids(now: datetime | None = None) -> list[str]:
        """O haftanın öne çıkan kozmetik id listesi (deterministik)."""
        now = now or datetime.now(timezone.utc)
        return _select_featured_ids(now)

    @staticmethod
    def discounted_price_for(cosmetic_id: str, now: datetime | None = None) -> int | None:
        """Kozmetik bu hafta öne çıkıyorsa indirimli coin fiyatı, değilse None.

        Cosmetics satın alma servisi bu fonksiyonla indirimi DOĞRULAR; istemciden
        gelen fiyata güvenilmez.
        """
        now = now or datetime.now(timezone.utc)
        if cosmetic_id not in FeaturedService.featured_ids(now):
            return None
        item = COSMETICS_BY_ID.get(cosmetic_id)
        if not item or not isinstance(item.get("price_coins"), int):
            return None
        return _discounted_price(item["price_coins"], FEATURED_DISCOUNT_PCT)

    @staticmethod
    async def get_featured(db: AsyncSession, user_id: str) -> dict:
        """GET /api/store/featured — haftalık rotasyonlu indirimli kozmetikler."""
        now = datetime.now(timezone.utc)
        seed, iso_year, iso_week = _iso_week_seed(now)
        owned = await CosmeticsService._owned_ids(db, user_id)

        items: list[dict] = []
        for cid in _select_featured_ids(now):
            item = COSMETICS_BY_ID.get(cid)
            if not item:
                continue
            original = item["price_coins"]
            discounted = _discounted_price(original, FEATURED_DISCOUNT_PCT)
            items.append({
                "cosmetic_id": cid,
                "slot": item["slot"],
                "name": item["name"],
                "original_price_coins": original,
                "discounted_price_coins": discounted,
                "discount_pct": FEATURED_DISCOUNT_PCT,
                "owned": cid in owned,
            })

        return {
            "week_id": _week_id(iso_year, iso_week),
            "expires_at": _week_end_utc(now).isoformat(),
            "items": items,
        }

    # --- Sınırlı süreli teklifler (LTO) ---
    @staticmethod
    def _build_offers(now: datetime) -> list[dict]:
        """O haftaya özel deterministik teklif(ler).

        Teklifler mevcut store kataloğundaki ürünlere (product_id) bağlanır;
        satın alma normal /store/purchase akışını kullanır. Fiyat/indirim
        backend'de doğrulanır.
        """
        seed, iso_year, iso_week = _iso_week_seed(now)
        expires_at = _week_end_utc(now).isoformat()
        week = _week_id(iso_year, iso_week)

        # Haftalık dönüşümlü iki teklif havuzu — deterministik seçim.
        # Hepsi mevcut katalog ürünlerine bağlı; pay-to-win YOK.
        pool = [
            {
                "offer_id": f"lto_gold_boost_{week}",
                "product_id": "gold_medium",      # mevcut katalog ürünü
                "title": "Haftalık Altın Fırsatı",
                "description": "9.000 altın, bu hafta avantajlı fiyatla (+%12 bonus dahil)",
                "contents": {"coins": 9000},
                "original_price_display": "₺79,99",
                "price_display": "₺59,99",
                "price_usd": "$5,99",
                "discount_pct": 25,
                "expires_at": expires_at,
            },
            {
                "offer_id": f"lto_premium_bundle_{week}",
                "product_id": "premium_monthly",  # mevcut katalog ürünü
                "title": "Premium Haftalık Paket",
                "description": "Aylık premium — reklamsız + günlük altın + premium çerçeve",
                "contents": {"premium_days": 30, "frame_cosmetic": "frame_neon"},
                "original_price_display": "₺99,99",
                "price_display": "₺79,99",
                "price_usd": "$4,99",
                "discount_pct": 20,
                "expires_at": expires_at,
            },
        ]
        # Her hafta havuzdan deterministik 1 teklif öne çıkar; ikincisi sabit
        # kalır → her zaman 2 aktif teklif ama içerik haftalık döner.
        rng = random.Random(seed)
        rng.shuffle(pool)
        return pool

    @staticmethod
    async def get_offers(db: AsyncSession, user_id: str) -> dict:
        """GET /api/store/offers — o an aktif zaman-sınırlı teklifler."""
        now = datetime.now(timezone.utc)
        return {"offers": FeaturedService._build_offers(now)}
