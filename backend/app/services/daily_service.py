"""Günlük ödül + seri (streak) iş mantığı.

UTC gün bazlı çalışır. Kullanıcı her UTC gününde bir kez ödül alabilir.
- Son alım DÜN ise seri (streak) +1 artar.
- Son alım BUGÜN ise zaten alınmış sayılır.
- 1 günden fazla boşluk varsa seri 1'e döner.

Ödül formülü: reward = min(50 + (streak - 1) * 25, 250)
(streak burada GÜNCELLENMİŞ/o gün geçerli olacak seri değeridir.)
"""

from datetime import date, datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from app.services.user_service import UserService

MAX_DAILY_REWARD = 250
BASE_DAILY_REWARD = 50
STEP_DAILY_REWARD = 25
# Premium kullanıcıların günlük ödülüne eklenen bonus coin (pay-to-win YOK).
PREMIUM_DAILY_BONUS = 100


def _is_premium_active(user, now: datetime) -> bool:
    """Kullanıcının premium'u şu an geçerli mi? (süre bazlı doğrulama)."""
    if not getattr(user, "is_premium", False):
        return False
    until = getattr(user, "premium_until", None)
    if until is None:
        # is_premium True ama süresiz işaretliyse premium kabul et.
        return True
    if until.tzinfo is None:
        until = until.replace(tzinfo=timezone.utc)
    return until > now


def _utc_date(dt: datetime | None) -> date | None:
    """Bir datetime'ı UTC gününe (date) çevirir; None ise None döner."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        # Naive damgalar UTC kabul edilir.
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).date()


def _reward_for_streak(streak: int) -> int:
    """Verilen seri için ödül miktarını hesaplar."""
    return min(BASE_DAILY_REWARD + (streak - 1) * STEP_DAILY_REWARD, MAX_DAILY_REWARD)


def _next_streak(last_claim_date: date | None, today: date) -> int:
    """Bugün alındığında geçerli olacak yeni seri değerini hesaplar.

    last_claim_date BUGÜN ise çağrılmamalıdır (zaten alınmış demektir);
    yine de güvenli davranır.
    """
    if last_claim_date is None:
        return 1
    delta_days = (today - last_claim_date).days
    if delta_days == 1:
        # Dün alınmış → seri devam ediyor (caller mevcut streak'i +1 yapar).
        return -1  # işaret: "devam et"
    if delta_days <= 0:
        # Bugün (ya da gelecekte) → değişmez (caller bunu zaten engeller).
        return -1
    # 1 günden fazla boşluk → seri sıfırlanır.
    return 1


class DailyService:
    """Günlük ödül durumu ve ödül talebi (claim) mantığı."""

    @staticmethod
    def _compute_state(user, now: datetime) -> dict:
        """Verilen kullanıcı için günlük ödül durumunu hesaplar (yan etkisiz).

        Returns:
            {
              can_claim: bool,
              effective_streak: int,   # claim edilirse geçerli olacak seri
              today_reward: int,       # claim edilirse verilecek ödül
              next_reward: int,        # bir sonraki günün ödülü
              last_claim_date: date|None,
            }
        """
        today = now.astimezone(timezone.utc).date()
        last_date = _utc_date(user.last_daily_claim_at)
        current_streak = user.daily_streak or 0

        if last_date == today:
            # Bugün zaten alınmış.
            effective_streak = current_streak if current_streak > 0 else 1
            return {
                "can_claim": False,
                "effective_streak": effective_streak,
                "today_reward": _reward_for_streak(effective_streak),
                "next_reward": _reward_for_streak(effective_streak + 1),
                "last_claim_date": last_date,
            }

        # Alınabilir; geçerli olacak seriyi hesapla.
        if last_date is None:
            effective_streak = 1
        else:
            delta_days = (today - last_date).days
            if delta_days == 1:
                effective_streak = current_streak + 1
            else:
                # delta_days > 1 (boşluk) → sıfırla.
                effective_streak = 1

        return {
            "can_claim": True,
            "effective_streak": effective_streak,
            "today_reward": _reward_for_streak(effective_streak),
            "next_reward": _reward_for_streak(effective_streak + 1),
            "last_claim_date": last_date,
        }

    @staticmethod
    async def get_status(db: AsyncSession, user_id: str) -> dict:
        """GET /api/daily/status yanıtını üretir."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        now = datetime.now(timezone.utc)
        state = DailyService._compute_state(user, now)

        return {
            "can_claim": state["can_claim"],
            "streak": user.daily_streak or 0,
            "today_reward": state["today_reward"],
            "next_reward": state["next_reward"],
            "last_claim_at": (
                user.last_daily_claim_at.isoformat()
                if user.last_daily_claim_at
                else None
            ),
        }

    @staticmethod
    async def claim(db: AsyncSession, user_id: str) -> dict:
        """POST /api/daily/claim — bugün alınmadıysa ödülü verir."""
        user = await UserService.get_user_by_id(db, user_id)
        if not user:
            raise ValueError("Kullanıcı bulunamadı.")

        now = datetime.now(timezone.utc)
        state = DailyService._compute_state(user, now)

        if not state["can_claim"]:
            return {
                "claimed": False,
                "reason": "already_claimed",
                "reward": 0,
                "streak": user.daily_streak or 0,
                "coins": user.coins,
            }

        base_reward = state["today_reward"]
        premium_bonus = PREMIUM_DAILY_BONUS if _is_premium_active(user, now) else 0
        reward = base_reward + premium_bonus
        user.daily_streak = state["effective_streak"]
        user.last_daily_claim_at = now
        user.coins = (user.coins or 0) + reward

        await db.flush()
        await db.refresh(user)

        return {
            "claimed": True,
            "reward": reward,
            "base_reward": base_reward,
            "premium_bonus": premium_bonus,
            "streak": user.daily_streak,
            "coins": user.coins,
        }
