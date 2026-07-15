"""Battle Pass / Sezon servisi — sezon config, ilerleme ve ödül mantığı.

ÖNEMLİ: Burası KESİNLİKLE pay-to-win DEĞİLDİR. Tüm ödüller kozmetik/altın
(yumuşak para ve görsel öğeler) — yani oyun içi bilgi avantajı (kolay soru,
ekstra süre, vb.) ASLA verilmez. Premium pass yalnızca daha cömert KOZMETİK ve
yumuşak para ödülleri açar; rekabet adaletini bozmaz.

Sezon config kod tarafında sabit tutulur (DB tablosu yok). İlerleme User
tablosundaki season_* alanlarında saklanır:
  - season_points: bu sezonda toplanan kümülatif puan
  - season_tier: season_points'e göre hesaplanan ulaşılmış kademe (0..30)
  - has_battle_pass: premium hattı açan pass sahipliği
  - season_claimed_free / season_claimed_premium: claim edilmiş tier listeleri

Ödül tipleri:
  {"type": "coins",    "amount": int}
  {"type": "cosmetic", "cosmetic_id": str}  # cosmetics_service kataloğundaki id
"""

from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic import UserCosmetic
from app.services.cosmetics_service import CATALOG_BY_ID
from app.services.user_service import UserService, _to_uuid

# --- Sezon sabitleri ---
SEASON_ID = 1
SEASON_TIERS = 30
# Sezonun bitişine kalan gün (basit sabit; ileride config'ten gelebilir).
SEASON_ENDS_IN_DAYS = 30

# Her tier için kümülatif gereken puan: tier i için i * POINTS_PER_TIER.
# KITLAŞTIRMA (ekonomi dengesi): eşik 200 → 1000. Ödül miktarları (free 100/
# 250/500, premium 200/300/600 + kozmetik) AYNI kalır; yalnızca eşik 5 katına
# çıktığı için PUAN-BAŞI altın kazancı ~%80 düşer ("her 1000 puanda 100 altın").
# Tier/ödül yapısı korunur, sadece hız yeniden ölçeklenir.
POINTS_PER_TIER = 1000


def _build_tiers() -> list[dict]:
    """30 kademelik sezon ödül tablosunu üretir.

    free_reward: ağırlıklı olarak coin (her tier coin verir; her 5'te bir
    daha büyük coin paketi). premium_reward: daha cömert coin +
    bazı tier'larda kozmetik (cosmetics_service kataloğundaki id'ler).
    """
    # Premium hatta dağıtılacak kozmetikler (katalogdaki gerçek id'ler).
    # Tier numarası -> cosmetic_id eşlemesi.
    premium_cosmetics = {
        3: "name_mint",
        7: "frame_gold",
        11: "fx_confetti",
        15: "frame_neon",
        19: "name_gold",
        23: "fx_hearts",
        27: "frame_fire",
        30: "name_rainbow",  # sezon finali: gökkuşağı isim
    }

    tiers: list[dict] = []
    for tier in range(1, SEASON_TIERS + 1):
        points_required = tier * POINTS_PER_TIER

        # --- Free hat (coin ağırlıklı) ---
        if tier % 10 == 0:
            free_reward = {"type": "coins", "amount": 500}
        elif tier % 5 == 0:
            free_reward = {"type": "coins", "amount": 250}
        else:
            free_reward = {"type": "coins", "amount": 100}

        # --- Premium hat (daha cömert + kozmetik) ---
        if tier in premium_cosmetics:
            premium_reward = {"type": "cosmetic", "cosmetic_id": premium_cosmetics[tier]}
        elif tier % 5 == 0:
            # Her 5 tier'da bir büyük altın ödülü; finale doğru artar.
            premium_reward = {"type": "coins", "amount": 300 if tier < 20 else 600}
        else:
            # Premium coin ödülü free'nin yaklaşık 2 katı.
            premium_reward = {"type": "coins", "amount": 200}

        tiers.append(
            {
                "tier": tier,
                "points_required": points_required,
                "free_reward": free_reward,
                "premium_reward": premium_reward,
            }
        )
    return tiers


# Sabit sezon tablosu (modül yüklenirken bir kez kurulur).
SEASON_TIERS_TABLE: list[dict] = _build_tiers()
TIER_BY_NUMBER: dict[int, dict] = {t["tier"]: t for t in SEASON_TIERS_TABLE}


class SeasonService:
    """Battle Pass / Sezon iş mantığı."""

    @staticmethod
    def calculate_tier(season_points: int) -> int:
        """season_points'e göre ulaşılmış en yüksek tier'ı döner (0..30).

        Her tier için points_required kümülatiftir; oyuncu o eşiği geçtiyse
        o tier'a ulaşmış sayılır.
        """
        tier = 0
        for t in SEASON_TIERS_TABLE:
            if season_points >= t["points_required"]:
                tier = t["tier"]
            else:
                break
        return tier

    @staticmethod
    async def add_points(db: AsyncSession, user_id: str, points: int) -> None:
        """Oyuncuya sezon puanı ekle ve tier'ı yeniden hesapla.

        Ödül OTOMATİK verilmez — oyuncu claim eder. Bu fonksiyon yalnızca
        season_points ve season_tier'i günceller. Hata oyun akışını bozmasın
        diye çağıran taraf try/except ile sarmalıdır.
        """
        if points <= 0:
            return
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            return
        # Premium: 2x sezon puanı (pay-to-win YOK — sadece ilerleme hızı).
        multiplier = 2 if SeasonService._is_premium_active(user) else 1
        user.season_points = (user.season_points or 0) + int(points) * multiplier
        user.season_tier = SeasonService.calculate_tier(user.season_points)
        await db.flush()

    @staticmethod
    def _is_premium_active(user) -> bool:
        """Kullanıcının premium'u şu an geçerli mi?"""
        if not getattr(user, "is_premium", False):
            return False
        until = getattr(user, "premium_until", None)
        if until is None:
            return True
        if until.tzinfo is None:
            until = until.replace(tzinfo=timezone.utc)
        return until > datetime.now(timezone.utc)

    @staticmethod
    def _claimed_set(user, track: str) -> set[int]:
        """Verilen hat için claim edilmiş tier numaralarını set olarak döner."""
        field = (
            user.season_claimed_premium
            if track == "premium"
            else user.season_claimed_free
        )
        return set(int(t) for t in (field or []))

    @staticmethod
    async def get_season(db: AsyncSession, user_id: str) -> dict:
        """GET /api/season yanıtını üretir."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        my_points = user.season_points or 0
        my_tier = SeasonService.calculate_tier(my_points)
        has_pass = bool(user.has_battle_pass)
        free_claimed = SeasonService._claimed_set(user, "free")
        premium_claimed = SeasonService._claimed_set(user, "premium")

        tiers: list[dict] = []
        for t in SEASON_TIERS_TABLE:
            n = t["tier"]
            reached = my_tier >= n
            free_is_claimed = n in free_claimed
            premium_is_claimed = n in premium_claimed
            tiers.append(
                {
                    "tier": n,
                    "points_required": t["points_required"],
                    "free_reward": t["free_reward"],
                    "premium_reward": t["premium_reward"],
                    "free_claimed": free_is_claimed,
                    "premium_claimed": premium_is_claimed,
                    "free_claimable": reached and not free_is_claimed,
                    "premium_claimable": (
                        reached and has_pass and not premium_is_claimed
                    ),
                }
            )

        return {
            "season_id": SEASON_ID,
            "ends_in_days": SEASON_ENDS_IN_DAYS,
            "my_points": my_points,
            "my_tier": my_tier,
            "has_battle_pass": has_pass,
            "tiers": tiers,
        }

    @staticmethod
    async def _grant_reward(db: AsyncSession, user, reward: dict) -> None:
        """Bir ödülü kullanıcıya uygular (coins artır veya kozmetik ekle)."""
        rtype = reward.get("type")
        if rtype == "coins":
            user.coins = (user.coins or 0) + int(reward.get("amount", 0))
        elif rtype == "cosmetic":
            cosmetic_id = reward.get("cosmetic_id")
            if cosmetic_id and cosmetic_id in CATALOG_BY_ID:
                # Zaten sahipse mükerrer kayıt eklemeyelim.
                result = await db.execute(
                    select(UserCosmetic.id).where(
                        UserCosmetic.user_id == user.id,
                        UserCosmetic.cosmetic_id == cosmetic_id,
                    )
                )
                if result.scalar_one_or_none() is None:
                    db.add(
                        UserCosmetic(user_id=user.id, cosmetic_id=cosmetic_id)
                    )

    @staticmethod
    async def claim(
        db: AsyncSession, user_id: str, tier: int, track: str
    ) -> dict:
        """POST /api/season/claim — bir tier ödülünü claim et.

        Koşullar: tier ulaşılmış + henüz claim edilmemiş + (premium ise pass
        sahibi). Aksi halde ValueError.

        Raises:
            ValueError: Geçersiz tier/track, ulaşılmamış, zaten claim edilmiş
                veya premium için pass yoksa.
        """
        if track not in ("free", "premium"):
            raise ValueError("Geçersiz hat (track). 'free' veya 'premium' olmalı.")

        tier_def = TIER_BY_NUMBER.get(int(tier))
        if not tier_def:
            raise ValueError("Geçersiz tier.")

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        my_tier = SeasonService.calculate_tier(user.season_points or 0)
        if my_tier < int(tier):
            raise ValueError("Bu kademeye henüz ulaşmadınız.")

        if track == "premium" and not user.has_battle_pass:
            raise ValueError("Premium ödüller için Battle Pass gerekli.")

        claimed = SeasonService._claimed_set(user, track)
        if int(tier) in claimed:
            raise ValueError("Bu ödülü zaten aldınız.")

        reward = (
            tier_def["premium_reward"]
            if track == "premium"
            else tier_def["free_reward"]
        )
        await SeasonService._grant_reward(db, user, reward)

        # claimed listesine ekle (yeni liste atayarak JSON kolonun
        # değiştiğini SQLAlchemy'nin algılamasını garanti et).
        claimed.add(int(tier))
        new_list = sorted(claimed)
        if track == "premium":
            user.season_claimed_premium = new_list
        else:
            user.season_claimed_free = new_list

        await db.flush()
        await db.refresh(user)

        return {
            "claimed": True,
            "reward": reward,
            "coins": user.coins or 0,
        }
