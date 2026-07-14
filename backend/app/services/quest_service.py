"""Günlük 3 Görev servisi — "yarın neden geri geleyim?"in ikinci ayağı.

Her gün TRT gece yarısında sıfırlanır. Sabit havuzdan kullanıcıya özel 3 görev
seçilir (seed = kullanıcı + gün → aynı gün aynı 3 görev, Redis silinse bile
yeniden aynısı üretilir). İlerleme maç sonu akışında ve Günün 5 Sorusu
gönderiminde güncellenir; ödül oyuncu "AL" deyince verilir (idempotent).

Neden Redis (Postgres değil)? İlerleme günlük çöp veridir, 48 saat sonra
değersizleşir; DailyChallenge ile aynı deseni izler ve migration gerektirmez.

Redis anahtarları:
- quests:{user_id}:{YYYY-MM-DD} → JSON {"progress": {...}, "claimed": [...]} (TTL 48h)

Coin havuzu: maç ödülünün günlük cap'inden (500) AYRIDIR — görevler günde bir
kez tamamlanabilir ve toplam üst sınırı yapısal olarak 225 altındır (en pahalı
üçlü), farm edilemez.
"""

from __future__ import annotations

import json
import logging
import random
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy.ext.asyncio import AsyncSession

from app.redis_client import get_redis
from app.services.user_service import UserService

logger = logging.getLogger(__name__)

_TRT_ZONE = ZoneInfo("Europe/Istanbul")  # UTC+3 — Günün 5 Sorusu ile aynı gün sınırı
_STATE_TTL = 172800  # 48 saat

# Günlük görev sayısı.
QUESTS_PER_DAY = 3

# --- Sabit görev havuzu ---
# id      : Redis'te ve /claim ucunda kullanılan kararlı anahtar.
# title   : Oyuncuya gösterilen metin.
# target  : İlerleme hedefi (progress >= target → tamamlandı).
# reward  : Tamamlanınca alınabilecek altın.
# emoji   : Kart ikonu.
QUEST_POOL: list[dict] = [
    {
        "id": "play_3_matches",
        "title": "3 maç oyna",
        "target": 3,
        "reward": 50,
        "emoji": "🎮",
    },
    {
        "id": "three_correct",
        "title": "Bir maçta 3 doğru bil",
        "target": 1,
        "reward": 50,
        "emoji": "🎯",
    },
    {
        "id": "reach_final",
        "title": "Finale kal",
        "target": 1,
        "reward": 75,
        "emoji": "🏁",
    },
    {
        "id": "play_daily_five",
        "title": "Günün 5 Sorusu'nu oyna",
        "target": 1,
        "reward": 50,
        "emoji": "🗓️",
    },
    {
        "id": "win_match",
        "title": "Bir maç kazan",
        "target": 1,
        "reward": 100,
        "emoji": "🏆",
    },
]

_QUEST_BY_ID = {q["id"]: q for q in QUEST_POOL}


# ---------------------------------------------------------------------------
# Gün + seçim
# ---------------------------------------------------------------------------

def today_key() -> str:
    """Bugünün TRT tarih anahtarı (YYYY-MM-DD)."""
    return datetime.now(tz=_TRT_ZONE).strftime("%Y-%m-%d")


def pick_quests(user_id: str, date_key: str) -> list[dict]:
    """Kullanıcı+gün için 3 görevi DETERMİNİSTİK seç.

    Seed sabit olduğu için Redis durumu kaybolsa bile aynı gün aynı 3 görev
    üretilir — oyuncunun görevleri gün içinde asla değişmez.
    """
    rng = random.Random(f"{date_key}:{user_id}")
    return rng.sample(QUEST_POOL, QUESTS_PER_DAY)


# ---------------------------------------------------------------------------
# Durum okuma/yazma
# ---------------------------------------------------------------------------

async def _load_state(user_id: str, date_key: str) -> dict:
    """{"progress": {id: int}, "claimed": [id]} — yoksa boş durum."""
    try:
        client = await get_redis()
        raw = await client.get(f"quests:{user_id}:{date_key}")
        if raw:
            data = json.loads(raw)
            return {
                "progress": dict(data.get("progress") or {}),
                "claimed": list(data.get("claimed") or []),
            }
    except Exception as exc:
        logger.warning("quest _load_state failed for %s: %s", user_id, exc)
    return {"progress": {}, "claimed": []}


async def _save_state(user_id: str, date_key: str, state: dict) -> None:
    try:
        client = await get_redis()
        await client.set(
            f"quests:{user_id}:{date_key}", json.dumps(state), ex=_STATE_TTL
        )
    except Exception as exc:
        logger.warning("quest _save_state failed for %s: %s", user_id, exc)


def _view(quest: dict, state: dict) -> dict:
    """Bir görevi mobil için serileştir (ilerleme + tamamlandı + alındı)."""
    progress = min(int(state["progress"].get(quest["id"], 0)), quest["target"])
    completed = progress >= quest["target"]
    return {
        "id": quest["id"],
        "title": quest["title"],
        "emoji": quest["emoji"],
        "target": quest["target"],
        "reward": quest["reward"],
        "progress": progress,
        "completed": completed,
        "claimed": quest["id"] in state["claimed"],
        "claimable": completed and quest["id"] not in state["claimed"],
    }


async def get_today(user_id: str) -> dict:
    """GET /api/quests/today — bugünün 3 görevi + ilerleme + ödül durumu."""
    date_key = today_key()
    state = await _load_state(user_id, date_key)
    quests = [_view(q, state) for q in pick_quests(user_id, date_key)]
    return {
        "date": date_key,
        "quests": quests,
        "claimable_count": sum(1 for q in quests if q["claimable"]),
        "completed_count": sum(1 for q in quests if q["completed"]),
        "total_reward": sum(q["reward"] for q in quests),
    }


# ---------------------------------------------------------------------------
# İlerleme kancaları
# ---------------------------------------------------------------------------

async def _advance(user_id: str, increments: dict[str, int]) -> None:
    """Yalnızca kullanıcının BUGÜNKÜ görevlerini ilgilendiren artışları uygula."""
    if not user_id or not increments:
        return
    date_key = today_key()
    active_ids = {q["id"] for q in pick_quests(user_id, date_key)}
    relevant = {k: v for k, v in increments.items() if k in active_ids and v > 0}
    if not relevant:
        return

    state = await _load_state(user_id, date_key)
    for quest_id, amount in relevant.items():
        target = _QUEST_BY_ID[quest_id]["target"]
        current = int(state["progress"].get(quest_id, 0))
        state["progress"][quest_id] = min(current + amount, target)
    await _save_state(user_id, date_key, state)


async def record_match_end(
    user_id: str,
    *,
    won: bool,
    correct_answers: int,
    reached_final: bool,
) -> None:
    """Maç sonu görev ilerlemesi (ws/game.py idempotent ödül bloğundan çağrılır).

    Hataları YUTAR — görev ilerlemesi maç akışını/ödülünü asla bozmamalı.
    """
    try:
        await _advance(user_id, {
            "play_3_matches": 1,
            "three_correct": 1 if int(correct_answers or 0) >= 3 else 0,
            "reach_final": 1 if reached_final else 0,
            "win_match": 1 if won else 0,
        })
    except Exception as exc:
        logger.warning("quest record_match_end failed for %s: %s", user_id, exc)


async def record_daily_challenge(user_id: str) -> None:
    """Günün 5 Sorusu oynanınca ilgili görevi tamamla (skor gönderiminden çağrılır)."""
    try:
        await _advance(user_id, {"play_daily_five": 1})
    except Exception as exc:
        logger.warning("quest record_daily_challenge failed for %s: %s", user_id, exc)


# ---------------------------------------------------------------------------
# Ödül alma (claim)
# ---------------------------------------------------------------------------

async def claim(db: AsyncSession, user_id: str, quest_id: str) -> dict:
    """POST /api/quests/{id}/claim — tamamlanmış görevin altınını ver (idempotent).

    Raises:
        ValueError: görev bugün aktif değil / kullanıcı yok.

    Returns:
        {claimed, reason?, reward, coins, quest_id}
        - claimed=False + reason='not_completed' → henüz tamamlanmadı.
        - claimed=False + reason='already_claimed' → ödül zaten alınmış.
    """
    date_key = today_key()
    active = {q["id"]: q for q in pick_quests(user_id, date_key)}
    quest = active.get(quest_id)
    if quest is None:
        raise ValueError("Bu görev bugün aktif değil.")

    state = await _load_state(user_id, date_key)
    progress = int(state["progress"].get(quest_id, 0))

    if quest_id in state["claimed"]:
        user = await UserService.get_user_by_id(db, user_id)
        return {
            "claimed": False,
            "reason": "already_claimed",
            "reward": 0,
            "coins": (user.coins if user else 0) or 0,
            "quest_id": quest_id,
        }

    if progress < quest["target"]:
        user = await UserService.get_user_by_id(db, user_id)
        return {
            "claimed": False,
            "reason": "not_completed",
            "reward": 0,
            "coins": (user.coins if user else 0) or 0,
            "quest_id": quest_id,
        }

    user = await UserService.get_user_by_id(db, user_id)
    if not user:
        raise ValueError("Kullanıcı bulunamadı.")

    # Önce "alındı" işaretini yaz: aynı anda gelen ikinci istek çift ödül almasın.
    state["claimed"].append(quest_id)
    await _save_state(user_id, date_key, state)

    reward = int(quest["reward"])
    try:
        user.coins = (user.coins or 0) + reward
        await db.flush()
        await db.refresh(user)
    except Exception:
        # Altın YAZILAMADI (DB hatası → get_db rollback yapacak). İşareti GERİ AL,
        # yoksa oyuncu görevi tamamlamış ama ödülünü sonsuza dek kaybetmiş olur.
        state["claimed"].remove(quest_id)
        await _save_state(user_id, date_key, state)
        raise

    return {
        "claimed": True,
        "reward": reward,
        "coins": user.coins,
        "quest_id": quest_id,
    }
