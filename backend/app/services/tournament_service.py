"""Turnuva modu + aylık ranked sezon servisi.

PAY-TO-WIN YOK (kritik ilke):
  - Turnuva girişi (altın) tek başına PUAN VERMEZ. Puan yalnızca maç
    performansından (sıralama) gelir. Giriş ücreti bir ödül havuzuna gitmez —
    SINK olarak yanar (kumar değil). Ödülleri sistem fonlar.
  - Turnuva maçında sorular baştan sona ZOR (difficulty>=3) ve kazanılan ranked
    sezon puanı 3x çarpanlıdır. Yani avantaj satılmaz; sadece "daha hızlı puan
    kazanma FIRSATI" + zorlu mod + statü/kozmetik ödülü.

Ranked sezon: app/utils/season_util.py (aylık ilk-pazartesi). Puanlar season_id
ile season_scores tablosunda tutulur → her sezon sıfırlanır. Battle Pass
(season_service.py / User.season_points) AYRI ve dokunulmadı.
"""

from __future__ import annotations

import json
import logging
import time

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.cosmetic import UserCosmetic
from app.models.tournament import SeasonScore, SeasonSettlement
from app.models.user import User
from app.services.user_service import UserService, _to_uuid
from app.utils.season_util import current_season, season_id_for

logger = logging.getLogger("app.tournament")

# --- Zor Mod (eski "turnuva") ekonomisi ---
# Giriş 150 → 100 altın. ARTIK SINK DEĞİL: girişler bir ÖDÜL HAVUZUNDA toplanır
# (aşağıdaki ZORMOD_* + compute_prize_pool). Modun eski ölüm sebebi girişin boşa
# yanmasıydı; artık kazananlar havuzdan altın alır.
TOURNAMENT_GOLD_COST = 100
# Zor Mod maçında ranked sezon puanı çarpanı (performansa BAĞLI; giriş tek başına
# puan vermez). Normal maç 1x.
TOURNAMENT_POINT_MULTIPLIER = 3

# --- Zor Mod ödül havuzu (config; oranlar SABİT) ---
# effektif_havuz = max(gerçek_girişler_toplamı, ZORMOD_MIN_POOL). Havuzun
# %80'i ödül dağıtılır, %20'si yanar (sink). Ödül dağıtılabilir kısım
# şampiyon/2./3.'ye 800/250/150 oranıyla (normalize) bölünür.
ZORMOD_PRIZE_SHARE = 0.8            # havuzun ödüle giden oranı (%80)
ZORMOD_PAYOUT_RATIOS = (800, 250, 150)  # şampiyon / 2. / 3. (normalize edilir)

# Turnuva maçında sorular bu zorluk eşiğinden (dahil) seçilir → GERÇEKTEN ZOR
# (4-5). Yeterli zor soru yoksa question_service kademeli olarak gevşetir
# (önce >=4, yetmezse >=3), maç asla iptal olmaz.
TOURNAMENT_MIN_DIFFICULTY = 4

# Normal (turnuva olmayan) maçta sorular bu üst sınıra kadar seçilir → kolay/orta
# (1-3). Turnuva 4-5 havuzundan gelir; böylece iki mod zorlukça net ayrışır.
NORMAL_MAX_DIFFICULTY = 3

# --- Turnuva bileti (money-safe giriş ücreti izleme) ---
# Giriş ücreti düşülünce Redis'te bir "pending" bilet açılır. Maç GERÇEKTEN
# başlayınca bilet "consumed" olur. Maç hiç başlamazsa (lobi iptal / oyunda
# hiç gerçek oyuncu bağlanmadı) bilet İADE edilir → altın geri verilir.
# Redis kullanılır (tablo/migration gerekmez): TTL ile orphan bilet de temizlenir.
_TICKET_KEY_PREFIX = "tournament:ticket:"
# Bilet ömrü: bir lobi + maç en fazla ~birkaç dakika sürer. 1 saat fazlasıyla
# güvenli; consumed/refunded olduktan sonra kısa TTL ile silinir.
_TICKET_TTL_PENDING = 3600       # pending bilet en fazla 1 saat yaşar
_TICKET_TTL_RESOLVED = 300       # consumed/refunded işareti 5 dk sonra silinir

# --- Yetim ("hiç bağlanmama") bilet süpürücü ---
# Pending biletleri SCAN'siz bulmak için bir index seti (ZSET) tutarız:
# üye = user_id, skor = created_at (unix ts). enter → ekle; consume/refund → çıkar.
# Süpürücü periyodik olarak skoru (now - _TICKET_SWEEP_AGE)'den eski üyeleri çeker
# ve iade eder. Mantık: maç ya hızlı consume olur ya da iptalde refund edilir;
# bu süredir hâlâ pending olan bilet => maç olmadı => güvenle iade.
_TICKET_PENDING_INDEX = "tournament:tickets:pending"
_TICKET_SWEEP_AGE = 600          # >10 dk pending kalmış bilet yetim sayılır
_TICKET_SWEEP_BATCH = 200        # bir taramada en fazla bu kadar bilet işle

# --- Sezon sonu ödülleri (sistem-fonlu; top sıralar) ---
# rank -> ödül paketi. Kozmetikler eksklüzif (cosmetics_service source=tournament).
SEASON_REWARDS: list[dict] = [
    {
        "min_rank": 1, "max_rank": 1, "title": "Şampiyon",
        "bonus_gold": 1500,
        "cosmetics": ["frame_champion", "name_champion", "fx_crown"],
        "badge": "champion",
    },
    {
        "min_rank": 2, "max_rank": 3, "title": "Finalist",
        "bonus_gold": 600,
        "cosmetics": ["frame_legend"],
        "badge": "finalist",
    },
    {
        "min_rank": 4, "max_rank": 7, "title": "Usta",
        "bonus_gold": 250,
        "cosmetics": [],
        "badge": "master",
    },
]


def _reward_for_rank(rank: int) -> dict | None:
    """1 tabanlı sıralamaya göre sezon sonu ödül paketini döner (yoksa None)."""
    for r in SEASON_REWARDS:
        if r["min_rank"] <= rank <= r["max_rank"]:
            return r
    return None


def compute_prize_pool(real_player_count: int) -> dict:
    """Zor Mod ödül havuzunu hesapla (sistem seed'li, %80 ödül / %20 sink).

    Adımlar:
      1. gerçek_girişler = real_player_count * TOURNAMENT_GOLD_COST.
      2. effektif_havuz = max(gerçek_girişler, ZORMOD_MIN_POOL)  ← sistem seed'i.
      3. dağıtılabilir = effektif_havuz * ZORMOD_PRIZE_SHARE      (%80; %20 yanar).
      4. şampiyon/2./3. payları = dağıtılabilir * (800/250/150) / 1200 (int'e yuvarlanır).

    Args:
        real_player_count: Maçtaki GERÇEK (bot olmayan) oyuncu sayısı.

    Returns:
        {"prize_pool": effektif_havuz(int),
         "prize_top3": [şampiyon_pay, ikinci_pay, üçüncü_pay] (int altın),
         "entries_total": gerçek_girişler_toplamı(int),
         "distributable": dağıtılabilir(int)}
    """
    from app.config import settings

    min_pool = int(getattr(settings, "ZORMOD_MIN_POOL", 1000))
    entries_total = max(0, int(real_player_count)) * TOURNAMENT_GOLD_COST
    effective_pool = max(entries_total, min_pool)
    distributable = effective_pool * ZORMOD_PRIZE_SHARE
    total_ratio = sum(ZORMOD_PAYOUT_RATIOS)
    prize_top3 = [
        int(distributable * r / total_ratio) for r in ZORMOD_PAYOUT_RATIOS
    ]
    return {
        "prize_pool": int(effective_pool),
        "prize_top3": prize_top3,
        "entries_total": int(entries_total),
        "distributable": int(distributable),
    }


class TournamentService:
    """Turnuva girişi, ranked sezon puanı, sezon leaderboard ve settlement."""

    # ------------------------------------------------------------------
    # Ranked sezon puanı (game engine buradan yazar)
    # ------------------------------------------------------------------

    @staticmethod
    async def add_season_points(
        db: AsyncSession,
        user_id: str,
        points: int,
        *,
        season_id: str | None = None,
    ) -> None:
        """Kullanıcıya MEVCUT ranked sezon puanı ekle (upsert; sezon ile ilişkili).

        Çağıran taraf turnuva ise puanı zaten 3x ile geçirir. points<=0 ise no-op.
        Hata oyun akışını bozmasın diye çağıran try/except ile sarmalı.
        """
        if points <= 0:
            return
        sid = season_id or season_id_for()
        uid = _to_uuid(user_id)
        row = (
            await db.execute(
                select(SeasonScore).where(
                    SeasonScore.user_id == uid,
                    SeasonScore.season_id == sid,
                )
            )
        ).scalar_one_or_none()
        if row is None:
            db.add(SeasonScore(user_id=uid, season_id=sid, points=int(points)))
        else:
            row.points = (row.points or 0) + int(points)
        await db.flush()

    # ------------------------------------------------------------------
    # Zor Mod maç-sonu ödül havuzu dağıtımı
    # ------------------------------------------------------------------

    @staticmethod
    async def grant_prize_pool(
        db: AsyncSession,
        ranked_user_ids: list[str],
        prize_top3: list[int],
    ) -> dict[str, int]:
        """Zor Mod ödül havuzunu ilk 3 GERÇEK oyuncuya altın olarak ver.

        ranked_user_ids skora göre AZALAN sıralı gerçek oyuncu id'leridir
        (şampiyon = 0. indeks). prize_top3 = [şampiyon_pay, 2._pay, 3._pay].
        Ödül maç ödülü GÜNLÜK CAP'inden BAĞIMSIZDIR (turnuva payoutu; sezon
        settlement bonus_gold gibi doğrudan bakiyeye eklenir).

        İdempotency ÇAĞIRANIN sorumluluğundadır: maç ödülleriyle aynı Redis
        (match:rewarded:{game_id}) korumalı blokta çağrılır → çift dağıtım olmaz.
        Commit ÇAĞIRAN tarafça yapılır.

        Returns:
            {user_id: verilen_altın} (yalnızca ödül alan ilk 3; 0 alanlar hariç).
        """
        awarded: dict[str, int] = {}
        for idx, prize in enumerate(prize_top3):
            if idx >= len(ranked_user_ids):
                break
            uid = ranked_user_ids[idx]
            amount = int(prize)
            if not uid or amount <= 0:
                continue
            try:
                user = await UserService.get_user_by_id(db, uid)
                if not user:
                    continue
                user.coins = (user.coins or 0) + amount
                awarded[uid] = amount
            except Exception as exc:  # tek oyuncu hatası diğerlerini engellemesin
                logger.warning("Zor Mod ödülü verilemedi (user %s): %s", uid, exc)
        return awarded

    # ------------------------------------------------------------------
    # Sezon leaderboard
    # ------------------------------------------------------------------

    @staticmethod
    def _entry(rank: int, user: User, points: int, points_to_next: int | None) -> dict:
        return {
            "rank": rank,
            "user_id": str(user.id),
            "username": user.username,
            "display_name": user.display_name or user.username,
            "avatar_id": user.avatar_id,
            "score": int(points),       # sezon puanı (mobil "score" alanını okur)
            "season_points": int(points),
            "level": user.level,
            "win_rate": user.win_rate,
            "points_to_next": points_to_next,
            # Kuşanılmış kozmetikler (mobil ile aynı anahtarlar). User satırları
            # leaderboard select / _my_entry tek select ile geldiği için N+1 yok.
            "frame": user.equipped_frame,
            "name_color": user.equipped_name_color,
            "effect": user.equipped_effect,
        }

    @staticmethod
    async def leaderboard(
        db: AsyncSession,
        *,
        user_id: str | None = None,
        limit: int = 100,
    ) -> dict:
        """GET /api/leaderboard/season — mevcut sezon sıralaması + my_entry.

        Deterministik tie-break (points desc, user_id asc); fallback YOK
        (sezon boşsa boş liste döner). leaderboard.py'deki düzeltmelerle tutarlı.
        """
        season = current_season()
        sid = season["season_id"]

        stmt = (
            select(SeasonScore.points, User)
            .join(User, User.id == SeasonScore.user_id)
            .where(
                SeasonScore.season_id == sid,
                SeasonScore.points > 0,
                User.is_active == True,  # noqa: E712
                User.deleted_at.is_(None),
                # Misafirler sıralamada listelenmez (puanları season_scores'ta
                # birikmeye devam eder; hesap kalıcılaşınca görünür olur).
                User.is_guest == False,  # noqa: E712
            )
            .order_by(SeasonScore.points.desc(), User.id.asc())
            .limit(limit)
        )
        rows = (await db.execute(stmt)).all()

        entries: list[dict] = []
        for i, (points, user) in enumerate(rows):
            ptn = None if i == 0 else int(rows[i - 1][0] - points)
            entries.append(TournamentService._entry(i + 1, user, points, ptn))

        my_entry = None
        if user_id:
            my_entry = await TournamentService._my_entry(db, sid, user_id)

        return {
            "period": "season",
            "season_id": sid,
            "season_start": season["season_start"],
            "season_end": season["season_end"],
            "seconds_left": season["seconds_left"],
            "entries": entries,
            "my_entry": my_entry,
            "total": len(entries),
        }

    @staticmethod
    async def _my_entry(db: AsyncSession, season_id: str, user_id: str) -> dict | None:
        """Kullanıcının mevcut sezon sıralamasındaki satırı (rank dahil)."""
        try:
            uid = _to_uuid(user_id)
        except Exception:
            return None
        me = (
            await db.execute(select(User).where(User.id == uid))
        ).scalar_one_or_none()
        if me is None:
            return None
        # Misafir sezon sıralamasında yer almaz → my_entry üretilmez
        # (leaderboard API'si response'a guest_hidden=true ekler).
        if me.is_guest:
            return None
        my_points = (
            await db.execute(
                select(SeasonScore.points).where(
                    SeasonScore.user_id == uid,
                    SeasonScore.season_id == season_id,
                )
            )
        ).scalar_one_or_none()
        if not my_points or my_points <= 0:
            # Bu sezon henüz puanı yok → sıralamada değil.
            return TournamentService._entry(0, me, 0, None)

        # Rank: aynı composite ölçütle (points desc, id asc) benden üstte kaç kişi.
        higher = (
            await db.scalar(
                select(func.count())
                .select_from(SeasonScore)
                .join(User, User.id == SeasonScore.user_id)
                .where(
                    SeasonScore.season_id == season_id,
                    SeasonScore.points > 0,
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                    User.is_guest == False,  # noqa: E712 — misafir rank'e sayılmaz
                    (
                        (SeasonScore.points > my_points)
                        | (
                            (SeasonScore.points == my_points)
                            & (SeasonScore.user_id < uid)
                        )
                    ),
                )
            )
        ) or 0
        rank = int(higher) + 1

        points_to_next = None
        if rank > 1:
            prev = await db.scalar(
                select(SeasonScore.points)
                .join(User, User.id == SeasonScore.user_id)
                .where(
                    SeasonScore.season_id == season_id,
                    SeasonScore.points > 0,
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                    User.is_guest == False,  # noqa: E712
                    (
                        (SeasonScore.points > my_points)
                        | (
                            (SeasonScore.points == my_points)
                            & (SeasonScore.user_id < uid)
                        )
                    ),
                )
                .order_by(SeasonScore.points.asc(), SeasonScore.user_id.desc())
                .limit(1)
            )
            if prev is not None:
                points_to_next = int(prev - my_points)

        return TournamentService._entry(rank, me, my_points, points_to_next)

    # ------------------------------------------------------------------
    # Turnuva bilgisi + giriş
    # ------------------------------------------------------------------

    @staticmethod
    async def info(db: AsyncSession, user_id: str) -> dict:
        """GET /api/tournament — turnuva modu bilgisi + sezon + senin sıran."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        season = current_season()
        my_entry = await TournamentService._my_entry(db, season["season_id"], user_id)

        rewards_preview = [
            {
                "rank_range": (
                    f"{r['min_rank']}"
                    if r["min_rank"] == r["max_rank"]
                    else f"{r['min_rank']}-{r['max_rank']}"
                ),
                "title": r["title"],
                "bonus_gold": r["bonus_gold"],
                "cosmetics": r["cosmetics"],
                "badge": r["badge"],
            }
            for r in SEASON_REWARDS
        ]

        # --- Zor Mod ödül havuzu önizlemesi (mobil lobide gösterir) ---
        # Havuz maçtaki gerçek oyuncu sayısına göre değişir; burada iki uç verilir:
        # garanti minimum (sistem seed'i) ve dolu lobi (MAX_PLAYERS) senaryosu.
        from app.config import settings

        min_pool_info = compute_prize_pool(0)  # 0 gerçek oyuncu → seed tabanı
        full_pool_info = compute_prize_pool(int(getattr(settings, "MAX_PLAYERS", 12)))
        prize_pool_info = {
            "entry_cost": TOURNAMENT_GOLD_COST,
            "min_pool": int(getattr(settings, "ZORMOD_MIN_POOL", 1000)),
            "prize_share": ZORMOD_PRIZE_SHARE,          # %80 ödül
            "sink_share": round(1 - ZORMOD_PRIZE_SHARE, 2),  # %20 yanar
            "payout_ratios": list(ZORMOD_PAYOUT_RATIOS),     # 800/250/150
            # Garanti minimum havuz (az oyunculu dönemde bile) + örnek dağıtım.
            "prize_pool": min_pool_info["prize_pool"],
            "prize_top3": min_pool_info["prize_top3"],
            # Dolu lobi senaryosu (mobil "en fazla bu kadar" gösterebilir).
            "max_prize_pool": full_pool_info["prize_pool"],
            "max_prize_top3": full_pool_info["prize_top3"],
        }

        return {
            "season_id": season["season_id"],
            "season_end": season["season_end"],
            "seconds_left": season["seconds_left"],
            "point_multiplier": TOURNAMENT_POINT_MULTIPLIER,
            "hard_mode": True,
            "description": (
                "Zor Mod'da sorular baştan sona zordur ve kazandığın sezon puanı "
                "3 katına çıkar. Girişler bir ÖDÜL HAVUZUNDA toplanır: kazananlar "
                "havuzdan altın alır (havuzun %80'i ödül). Giriş tek başına puan "
                "vermez — iyi oynamak şart."
            ),
            "entry_options": [
                {"currency": "gold", "cost": TOURNAMENT_GOLD_COST,
                 "affordable": (user.coins or 0) >= TOURNAMENT_GOLD_COST},
            ],
            "balances": {"gold": user.coins or 0},
            # Detaylı havuz bilgisi (oranlar, min/max senaryolar).
            "prize_pool_info": prize_pool_info,
            # Mobil sözleşmesi TOP-LEVEL `prize_pool` + `prize_top3` bekliyor
            # (tournament_provider bunları kökten okur). prize_pool_info
            # içindeki garanti-minimum değerleri buraya aynalıyoruz — nested
            # detay da dursun, mobil de bozulmasın.
            "prize_pool": prize_pool_info["prize_pool"],
            "prize_top3": prize_pool_info["prize_top3"],
            "my_entry": my_entry,
            "rewards_preview": rewards_preview,
        }

    # ------------------------------------------------------------------
    # Turnuva bileti (money-safe: düş → pending; başla → consumed; iptal → refund)
    # ------------------------------------------------------------------

    @staticmethod
    def _ticket_key(user_id: str) -> str:
        return f"{_TICKET_KEY_PREFIX}{user_id}"

    @staticmethod
    async def get_pending_ticket(user_id: str) -> dict | None:
        """Kullanıcının AKTİF (pending) turnuva biletini döner (yoksa None).

        Hata olursa None (Redis erişilemezse giriş bloklanmasın). Sadece
        status=="pending" olan bilet "aktif" sayılır.
        """
        try:
            from app.redis_client import get_redis

            redis = await get_redis()
            raw = await redis.get(TournamentService._ticket_key(user_id))
        except Exception as exc:  # pragma: no cover
            logger.warning("Turnuva bileti okunamadı (user %s): %s", user_id, exc)
            return None
        if not raw:
            return None
        try:
            ticket = json.loads(raw)
        except Exception:
            return None
        return ticket if ticket.get("status") == "pending" else None

    @staticmethod
    async def _write_ticket(user_id: str, ticket: dict, ttl: int) -> None:
        from app.redis_client import get_redis

        redis = await get_redis()
        await redis.set(
            TournamentService._ticket_key(user_id),
            json.dumps(ticket),
            ex=ttl,
        )

    @staticmethod
    async def _index_add_pending(user_id: str, created_at: float) -> None:
        """Pending bileti süpürücü index setine (ZSET) ekle. Hata sessiz."""
        try:
            from app.redis_client import get_redis

            redis = await get_redis()
            await redis.zadd(_TICKET_PENDING_INDEX, {user_id: created_at})
        except Exception as exc:  # pragma: no cover
            logger.warning("Pending index eklenemedi (user %s): %s", user_id, exc)

    @staticmethod
    async def _index_remove_pending(user_id: str) -> None:
        """Kullanıcıyı pending index setinden çıkar (consume/refund sonrası)."""
        try:
            from app.redis_client import get_redis

            redis = await get_redis()
            await redis.zrem(_TICKET_PENDING_INDEX, user_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Pending index'ten çıkarılamadı (user %s): %s", user_id, exc)

    @staticmethod
    async def consume_ticket(user_id: str) -> None:
        """Maç GERÇEKTEN başladığında bileti tüket (artık iade edilmez).

        Pending bilet yoksa no-op. Hata oyun akışını bozmasın diye sessiz.
        """
        try:
            ticket = await TournamentService.get_pending_ticket(user_id)
            if ticket is None:
                return
            ticket["status"] = "consumed"
            ticket["consumed_at"] = time.time()
            await TournamentService._write_ticket(
                user_id, ticket, _TICKET_TTL_RESOLVED
            )
            await TournamentService._index_remove_pending(user_id)
        except Exception as exc:  # pragma: no cover
            logger.warning("Turnuva bileti tüketilemedi (user %s): %s", user_id, exc)

    @staticmethod
    async def refund_ticket(db: AsyncSession, user_id: str) -> bool:
        """Pending bileti İADE et: altını geri ver, status=refunded.

        Maç hiç başlamadan iptal olduğunda çağrılır (lobi iptal / oyunda hiç
        gerçek oyuncu yok). Sadece status==pending bilet iade edilir → çift iade
        olmaz (idempotent). Commit ÇAĞIRAN tarafça yapılır.

        Returns:
            True iade yapıldıysa, False (bilet yok / zaten çözülmüş) ise.
        """
        ticket = await TournamentService.get_pending_ticket(user_id)
        if ticket is None:
            return False

        amount = int(ticket.get("amount", 0))
        if amount <= 0:
            return False

        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            return False

        user.coins = (user.coins or 0) + amount
        await db.flush()

        ticket["status"] = "refunded"
        ticket["refunded_at"] = time.time()
        try:
            await TournamentService._write_ticket(
                user_id, ticket, _TICKET_TTL_RESOLVED
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("İade bileti işaretlenemedi (user %s): %s", user_id, exc)
        # Süpürücü index'inden çıkar (artık pending değil; tekrar süpürülmesin).
        await TournamentService._index_remove_pending(user_id)
        logger.info(
            "Turnuva iadesi: user=%s %d altın geri verildi (maç başlamadı)",
            user_id, amount,
        )
        return True

    @staticmethod
    async def refund_pending_for_users(user_ids: list[str]) -> int:
        """Birden çok kullanıcının pending biletini iade et (kendi session'ı).

        Lobi/oyun iptal noktalarından çağrılır. Tüm iadeleri tek transaction'da
        yapıp commit eder. Hata akışı bozmasın diye tüm gövde try/except sarılı.

        Returns:
            İade edilen bilet sayısı.
        """
        # user_id'leri olan (bot olmayan) tekil kullanıcılar.
        uids = [u for u in dict.fromkeys(user_ids) if u]
        if not uids:
            return 0
        refunded = 0
        try:
            from app.database import async_session_factory

            async with async_session_factory() as db:
                for uid in uids:
                    try:
                        if await TournamentService.refund_ticket(db, uid):
                            refunded += 1
                    except Exception as exc:  # tek kullanıcı hatası diğerlerini bozmasın
                        logger.warning(
                            "Turnuva iadesi başarısız (user %s): %s", uid, exc
                        )
                await db.commit()
        except Exception as exc:  # pragma: no cover
            logger.warning("Toplu turnuva iadesi başarısız: %s", exc)
        return refunded

    @staticmethod
    async def enter(db: AsyncSession, user_id: str, currency: str = "gold") -> dict:
        """POST /api/tournament/enter — giriş ücretini düş (altın).

        Giriş ücreti SINK olarak yanar (ödül havuzuna gitmez; kumar değil). Puan
        VERMEZ. Yetersiz bakiyede ValueError. Maça katılım istemci tarafında WS
        lobisine ``mode=tournament`` ile bağlanarak yapılır (bu uç sadece bakiyeyi
        düşürüp turnuva oturumunu açar). ``currency`` parametresi geriye dönük
        uyumluluk için kabul edilir ama ne gelirse gelsin altın gibi davranır.

        IDEMPOTENCY (çift altın düşmesi koruması): Kullanıcının zaten AKTİF
        (pending) bir bileti varsa yeni ücret DÜŞÜLMEZ — mevcut bilet "tekrar"
        döndürülür. Bilet maç başlayınca consume, başlamazsa refund edilir
        (money-safe).

        Returns:
            {"entered": True, "currency", "cost", "gold", "season_id",
             "ticket_id", "reused": bool}
        """
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        # --- Idempotency: aktif pending bilet varsa ikinci kez DÜŞME ---
        existing = await TournamentService.get_pending_ticket(user_id)
        if existing is not None:
            return {
                "entered": True,
                "reused": True,
                "currency": "gold",
                "cost": int(existing.get("amount", 0)),
                "gold": user.coins or 0,
                "season_id": existing.get("season_id", season_id_for()),
                "point_multiplier": TOURNAMENT_POINT_MULTIPLIER,
                "ticket_id": existing.get("ticket_id"),
            }

        cost = TOURNAMENT_GOLD_COST
        if (user.coins or 0) < cost:
            raise ValueError("Yetersiz altın.")
        user.coins = (user.coins or 0) - cost

        await db.flush()
        await db.refresh(user)

        # --- Pending bilet aç (maç başlamazsa iade için izlenir) ---
        sid = season_id_for()
        ticket_id = f"{user_id}:{int(time.time() * 1000)}"
        ticket = {
            "ticket_id": ticket_id,
            "user_id": user_id,
            "currency": "gold",
            "amount": cost,
            "season_id": sid,
            "status": "pending",
            "created_at": time.time(),
        }
        try:
            await TournamentService._write_ticket(
                user_id, ticket, _TICKET_TTL_PENDING
            )
        except Exception as exc:  # pragma: no cover
            # Bilet yazılamazsa iade izlenemez. Money-safe davranış: ücreti
            # geri al ve hata ver (kullanıcı tekrar denesin) — altın yanmasın.
            logger.warning("Turnuva bileti yazılamadı (user %s): %s", user_id, exc)
            user.coins = (user.coins or 0) + cost
            await db.flush()
            raise ValueError(
                "Turnuva girişi geçici olarak yapılamadı, lütfen tekrar deneyin."
            ) from exc

        # Süpürücü index'ine ekle (yetim/“hiç bağlanmama” bileti iadesi için).
        # Index yazılamasa bile bilet TTL'i + çekirdek refund yolları korur; bu
        # yalnızca yetim biletin iadesini garanti eden ek emniyet ağıdır.
        await TournamentService._index_add_pending(user_id, ticket["created_at"])

        return {
            "entered": True,
            "reused": False,
            "currency": "gold",
            "cost": cost,
            "gold": user.coins or 0,
            "season_id": sid,
            "point_multiplier": TOURNAMENT_POINT_MULTIPLIER,
            "ticket_id": ticket_id,
        }

    # ------------------------------------------------------------------
    # Sezon sonu settlement (idempotent)
    # ------------------------------------------------------------------

    @staticmethod
    async def settle_season(db: AsyncSession, season_id: str) -> dict:
        """Bir ranked sezonu kapat: top sıralara ödül dağıt (idempotent).

        - Aynı season_id iki kez ödüllendirilmez (season_settlements kaydı).
        - Ödüller sistem-fonlu: bonus altın + eksklüzif kozmetik (zaten varsa
          mükerrer eklenmez) + unvan (response'ta döner; mobil rozet gösterir).
        - Commit ÇAĞIRAN tarafça yapılır.

        Returns:
            {"settled": bool, "already": bool, "season_id", "rewarded_count",
             "winners": [{user_id, rank, title, bonus_gold, cosmetics}]}
        """
        # Idempotency: settlement satırı varsa zaten dağıtılmış.
        existing = (
            await db.execute(
                select(SeasonSettlement).where(
                    SeasonSettlement.season_id == season_id
                )
            )
        ).scalar_one_or_none()
        if existing is not None:
            return {
                "settled": False,
                "already": True,
                "season_id": season_id,
                "rewarded_count": existing.rewarded_count,
                "winners": [],
            }

        max_rank = max(r["max_rank"] for r in SEASON_REWARDS)
        rows = (
            await db.execute(
                select(SeasonScore.points, User)
                .join(User, User.id == SeasonScore.user_id)
                .where(
                    SeasonScore.season_id == season_id,
                    SeasonScore.points > 0,
                    User.is_active == True,  # noqa: E712
                    User.deleted_at.is_(None),
                    # Misafir sezon sonu ödül hesabına KARIŞMAZ (sıralamada da
                    # görünmediği için tutarlı: ödül top-N görünen sıraya gider).
                    User.is_guest == False,  # noqa: E712
                )
                .order_by(SeasonScore.points.desc(), User.id.asc())
                .limit(max_rank)
            )
        ).all()

        winners: list[dict] = []
        for i, (points, user) in enumerate(rows):
            rank = i + 1
            reward = _reward_for_rank(rank)
            if not reward:
                continue
            # Bonus altın (sistem-fonlu).
            user.coins = (user.coins or 0) + int(reward["bonus_gold"])
            # Eksklüzif kozmetikler (mükerrer ekleme yok).
            granted_cosmetics: list[str] = []
            for cid in reward["cosmetics"]:
                exists = (
                    await db.execute(
                        select(UserCosmetic.id).where(
                            UserCosmetic.user_id == user.id,
                            UserCosmetic.cosmetic_id == cid,
                        )
                    )
                ).scalar_one_or_none()
                if exists is None:
                    db.add(UserCosmetic(user_id=user.id, cosmetic_id=cid))
                    granted_cosmetics.append(cid)
            winners.append(
                {
                    "user_id": str(user.id),
                    "rank": rank,
                    "title": reward["title"],
                    "bonus_gold": reward["bonus_gold"],
                    "cosmetics": granted_cosmetics,
                    "badge": reward["badge"],
                }
            )

        # Idempotency işareti (winners boş olsa bile yaz → sezon işlendi sayılır).
        db.add(
            SeasonSettlement(season_id=season_id, rewarded_count=len(winners))
        )
        await db.flush()

        return {
            "settled": True,
            "already": False,
            "season_id": season_id,
            "rewarded_count": len(winners),
            "winners": winners,
        }

    @staticmethod
    async def settle_due_seasons() -> dict:
        """Bitmiş ama henüz settle edilmemiş geçmiş sezon(lar)ı kapat (lazy).

        Startup'ta veya periyodik tetiklenir. Bir önceki ranked sezonu kontrol
        eder; settle edilmemişse ödülleri dağıtır (idempotent). Kendi DB session'ını
        açar ve commit eder. Hata startup'ı bozmasın diye çağıran tarafça
        try/except ile sarmalıdır.

        Returns:
            settle_season sonucu (veya {"settled": False} no-op'ta).
        """
        from app.database import async_session_factory
        from app.utils.season_util import current_season, previous_season_id

        prev_sid = previous_season_id(current_season()["season_id"])
        async with async_session_factory() as db:
            result = await TournamentService.settle_season(db, prev_sid)
            await db.commit()
        if result.get("settled"):
            logger.info(
                "Ranked sezon %s settle edildi: %d kullanıcı ödüllendirildi",
                prev_sid, result.get("rewarded_count", 0),
            )
        return result

    # ------------------------------------------------------------------
    # Yetim ("hiç bağlanmama") bilet süpürücü (money-safe; idempotent)
    # ------------------------------------------------------------------

    @staticmethod
    async def sweep_orphan_tickets(*, max_age: int = _TICKET_SWEEP_AGE) -> int:
        """>max_age sn'dir pending kalmış (yetim) biletleri iade et.

        Senaryo: kullanıcı /enter yaptı (altın düştü, bilet=pending) ama lobiye HİÇ
        bağlanmadı → ne consume ne refund tetiklendi. Bu süpürücü, pending index
        setinden (ZSET; skor=created_at) eski üyeleri SCAN'siz çeker ve iade eder.

        IDEMPOTENT: iade mantığı yalnızca status==pending bileti iade eder
        (refund_ticket). İki süpürme çakışsa bile ilk iade bileti "refunded"
        yapıp index'ten çıkarır → ikincisi no-op olur (çift iade yok). consumed
        bilet zaten index'te DEĞİLDİR (consume'da çıkarıldı) → iade EDİLMEZ.

        Returns:
            İade edilen yetim bilet sayısı.
        """
        try:
            from app.redis_client import get_redis

            redis = await get_redis()
            cutoff = time.time() - max_age
            # Skoru cutoff'tan eski (created_at <= cutoff) üyeler = yeterince yaşlı.
            stale = await redis.zrangebyscore(
                _TICKET_PENDING_INDEX, 0, cutoff, start=0, num=_TICKET_SWEEP_BATCH
            )
        except Exception as exc:  # pragma: no cover
            logger.warning("Yetim bilet taraması başarısız: %s", exc)
            return 0

        # ZSET üyeleri str user_id (decode_responses=True). Boşsa no-op.
        user_ids = [u for u in (stale or []) if u]
        if not user_ids:
            return 0

        # refund_pending_for_users zaten kendi session'ında, idempotent iade yapar
        # ve refund_ticket içinden index'ten çıkarır. Sadece gerçekten pending
        # olanlar iade edilir (consumed/refunded => no-op).
        refunded = await TournamentService.refund_pending_for_users(user_ids)

        # Güvenlik: pending OLMAYAN ama hâlâ index'te kalmış üyeleri de temizle
        # (ör. consume sırasında index çıkarma başarısız olduysa). refund_ticket
        # zaten pending olanları çıkardı; geri kalanları burada düşür.
        try:
            from app.redis_client import get_redis

            redis = await get_redis()
            for uid in user_ids:
                if await TournamentService.get_pending_ticket(uid) is None:
                    await redis.zrem(_TICKET_PENDING_INDEX, uid)
        except Exception as exc:  # pragma: no cover
            logger.warning("Yetim index temizliği başarısız: %s", exc)

        if refunded:
            logger.info(
                "Yetim turnuva bileti süpürücü: %d bilet iade edildi (>%d sn pending)",
                refunded, max_age,
            )
        return refunded
