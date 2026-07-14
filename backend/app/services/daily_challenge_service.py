"""Daily Challenge service — same 5 questions for all players on a given day.

Each day at midnight TRT (UTC+3), a new set of 5 questions is selected.
Players can play the daily challenge once per day.
Scores go to a separate leaderboard, not the main one.

COIN ÖDÜLÜ (retention omurgası): tamamlayınca taban 100 altın + her doğru için
20 altın → 5/5 doğru = 200 altın. Günde BİR kez (Redis SET NX ile idempotent).

Ödül havuzu kararı — maç ödülünün günlük cap'inden (MATCH_REWARD_DAILY_CAP=500)
AYRIDIR. Gerekçe: o cap tekrar tekrar oynanabilen maçlar için bir anti-farm
önlemidir; Günün 5 Sorusu doğası gereği günde bir kez oynanır ve üst sınırı
zaten yapısal olarak 200 altındır — farm edilemez. Aynı havuza konsaydı, cap'i
dolduran EN AKTİF oyuncular günlük sorudan hiç altın alamaz, yani geri dönüş
teşviki tam da en sadık kullanıcıda çalışmazdı. Bu yüzden ayrı havuz.

Redis keys:
- daily_challenge:{YYYY-MM-DD}           → JSON list of 5 question dicts (TTL 48h)
- daily_challenge_played:{user_id}:{YYYY-MM-DD} → "1" (TTL 48h, marks as played)
- daily_challenge_score:{YYYY-MM-DD}     → Sorted Set {user_id: score} (TTL 8 days)
- daily_challenge_result:{user_id}:{YYYY-MM-DD} → JSON sonuç (paylaşım kartı, TTL 48h)
- daily_challenge_streak:{user_id}       → JSON {streak, last_date} (TTL 60 gün)
"""

import json
import logging
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

from app.redis_client import get_redis

logger = logging.getLogger(__name__)

_TRT_ZONE = ZoneInfo("Europe/Istanbul")  # UTC+3
_QUESTIONS_TTL = 172800   # 48 hours
_PLAYED_TTL = 172800      # 48 hours
_RESULT_TTL = 172800      # 48 hours
_STREAK_TTL = 5184000     # 60 gün (seri kopunca zaten sıfırlanır)
_LEADERBOARD_TTL = 691200  # 8 days

# --- Coin ödülü (ayrı havuz; bkz. modül başlığı) ---
DAILY_CHALLENGE_BASE_REWARD = 100   # tamamlama tabanı
DAILY_CHALLENGE_PER_CORRECT = 20    # her doğru için ek
DAILY_CHALLENGE_MAX_REWARD = (
    DAILY_CHALLENGE_BASE_REWARD + 5 * DAILY_CHALLENGE_PER_CORRECT
)  # 200


def reward_for_correct_count(correct_count: int) -> int:
    """Doğru sayısını coin ödülüne çevir (taban 100 + doğru başına 20, maks 200)."""
    safe = max(0, min(5, int(correct_count)))
    return DAILY_CHALLENGE_BASE_REWARD + safe * DAILY_CHALLENGE_PER_CORRECT


# ---------------------------------------------------------------------------
# Internal helper — same mock questions used in game.py
# ---------------------------------------------------------------------------

def _get_fallback_questions() -> list[dict]:
    """Return a set of 5 questions for daily challenge when no DB is available."""
    return [
        {
            "id": "daily_1",
            "type": "dogru_yanlis",
            "content": "İstanbul Türkiye'nin en kalabalık şehridir.",
            "question": "İstanbul Türkiye'nin en kalabalık şehridir.",
            "options": ["Doğru", "Yanlış"],
            "correct_answer": 0,
            "time_seconds": 5,
        },
        {
            "id": "daily_2",
            "type": "gorsel",
            "content": "Bu hangi ülkenin bayrağıdır?",
            "question": "Bu hangi ülkenin bayrağıdır?",
            "options": ["Türkiye", "Azerbaycan", "Kıbrıs", "Özbekistan"],
            "correct_answer": 0,
            "time_seconds": 7,
        },
        {
            "id": "daily_3",
            "type": "karsilastirma",
            "content": "Hangisi daha büyük bir şehir?",
            "question": "Hangisi daha büyük bir şehir?",
            "options": ["Ankara", "İzmir"],
            "correct_answer": 0,
            "time_seconds": 7,
        },
        {
            "id": "daily_4",
            "type": "coktan_secmeli",
            "content": "Türkiye'nin resmi dili hangisidir?",
            "question": "Türkiye'nin resmi dili hangisidir?",
            "options": ["Kürtçe", "Türkçe", "Arapça", "Farsça"],
            "correct_answer": 1,
            "time_seconds": 8,
        },
        {
            "id": "daily_5",
            "type": "tahmin",
            "content": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "question": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "options": None,
            "correct_answer": 85,
            "real_answer": 85,
            "min_value": 50,
            "max_value": 120,
            "unit": "milyon",
            "time_seconds": 8,
        },
    ]


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

async def get_today_key() -> str:
    """Return today's date string in TRT timezone (YYYY-MM-DD).

    TRT is UTC+3. The daily challenge resets at midnight Istanbul time.
    """
    now_trt = datetime.now(tz=_TRT_ZONE)
    return now_trt.strftime("%Y-%m-%d")


async def get_today_questions() -> list[dict]:
    """Return today's 5 questions, generating and caching them if not set.

    Questions are shared across all players on the same day.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge:{date_key}"
    try:
        client = await get_redis()
        raw = await client.get(redis_key)
        if raw:
            return json.loads(raw)

        # Not cached yet — generate and cache
        questions = _get_fallback_questions()
        await set_today_questions(questions)
        return questions
    except Exception as exc:
        logger.warning("daily_challenge get_today_questions failed: %s", exc)
        return _get_fallback_questions()


async def set_today_questions(questions: list[dict]) -> None:
    """Cache today's questions to Redis with a 48-hour TTL.

    Args:
        questions: List of 5 question dicts to cache.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge:{date_key}"
    try:
        client = await get_redis()
        await client.set(redis_key, json.dumps(questions), ex=_QUESTIONS_TTL)
    except Exception as exc:
        logger.warning("daily_challenge set_today_questions failed: %s", exc)


async def has_played_today(user_id: str) -> bool:
    """Check if the user has already played today's daily challenge.

    Returns:
        True if the user played today, False otherwise.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge_played:{user_id}:{date_key}"
    try:
        client = await get_redis()
        return await client.exists(redis_key) > 0
    except Exception as exc:
        logger.warning("daily_challenge has_played_today failed for %s: %s", user_id, exc)
        return False


async def mark_as_played(user_id: str) -> None:
    """Record that the user has completed today's daily challenge.

    Sets a 48-hour TTL flag so the record expires naturally.
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge_played:{user_id}:{date_key}"
    try:
        client = await get_redis()
        await client.set(redis_key, "1", ex=_PLAYED_TTL)
    except Exception as exc:
        logger.warning("daily_challenge mark_as_played failed for %s: %s", user_id, exc)


async def submit_score(user_id: str, score: int) -> int:
    """Add the player's score to today's daily challenge leaderboard.

    Args:
        user_id: The player's unique identifier.
        score:   The score achieved in the daily challenge.

    Returns:
        The player's 1-based rank after submission (1 = highest score).
    """
    date_key = await get_today_key()
    leaderboard_key = f"daily_challenge_score:{date_key}"
    try:
        client = await get_redis()
        # ZADD with score; higher score = better rank (use positive score)
        await client.zadd(leaderboard_key, {user_id: score})
        await client.expire(leaderboard_key, _LEADERBOARD_TTL)

        # Rank: count players with strictly higher score + 1
        # Redis ZREVRANK gives 0-based descending rank
        rank_zero = await client.zrevrank(leaderboard_key, user_id)
        return (rank_zero + 1) if rank_zero is not None else 1
    except Exception as exc:
        logger.warning("daily_challenge submit_score failed for %s: %s", user_id, exc)
        return 0


async def try_mark_played(user_id: str) -> bool:
    """Bugünün oynama hakkını ATOMİK olarak rezerve et (SET NX).

    İdempotency'nin kalbi: aynı kullanıcı aynı gün iki kez skor gönderirse
    (çift dokunuş, ağ tekrarı) İKİNCİ çağrı False döner → coin bir kez verilir.

    Returns:
        True  — hak bu çağrıda alındı (ödül verilebilir).
        False — bugün zaten oynanmış (ödül YOK).
    """
    date_key = await get_today_key()
    redis_key = f"daily_challenge_played:{user_id}:{date_key}"
    try:
        client = await get_redis()
        first = await client.set(redis_key, "1", ex=_PLAYED_TTL, nx=True)
        return first is not None
    except Exception as exc:
        logger.warning("daily_challenge try_mark_played failed for %s: %s", user_id, exc)
        # Redis yoksa oyuncuyu cezalandırma: oynasın (ödül best-effort verilir).
        return True


# ---------------------------------------------------------------------------
# Cevap değerlendirme (paylaşım kartının 🟩🟥 ızgarası buradan çıkar)
# ---------------------------------------------------------------------------

def _tolerance_for(question: dict) -> float:
    """Tahmin (slider) sorusu için tolerans bandı — maç motoruyla AYNI kural.

    Aralığın %10'u; aralık yoksa |doğru cevap|'ın %10'u; o da yoksa 1.0 taban.
    """
    real = float(question.get("real_answer", question.get("correct_answer", 0)) or 0)
    min_val = question.get("min_value")
    max_val = question.get("max_value")
    if min_val is not None and max_val is not None and float(max_val) > float(min_val):
        return 0.10 * (float(max_val) - float(min_val))
    return max(0.10 * abs(real), 1.0)


def grade_answers(questions: list[dict], answers: list) -> list[bool]:
    """Oyuncunun cevaplarını SUNUCUDA değerlendir → [True, False, ...] dizisi.

    Doğru cevaplar istemciye HİÇ gönderilmez (games.py onları soyar); bu yüzden
    doğru/yanlış kararı yalnızca burada verilir — istemci "5/5 yaptım" diyemez.

    Args:
        questions: Günün soruları (correct_answer/real_answer DAHİL).
        answers:   Soru sırasıyla cevaplar. Şıklı tiplerde index (int),
                   'tahmin' tipinde sayı. Cevapsız/geçersiz → yanlış.

    Returns:
        Soru sayısı kadar bool listesi (eksik cevap = False).
    """
    results: list[bool] = []
    for i, q in enumerate(questions):
        given = answers[i] if i < len(answers) else None
        if given is None:
            results.append(False)
            continue
        try:
            if q.get("type") == "tahmin":
                real = float(q.get("real_answer", q.get("correct_answer", 0)) or 0)
                results.append(abs(float(given) - real) <= _tolerance_for(q))
            else:
                results.append(int(given) == int(q.get("correct_answer", -1)))
        except (TypeError, ValueError):
            results.append(False)
    return results


# ---------------------------------------------------------------------------
# Seri (streak) — "kaç gün üst üste Günün 5 Sorusu'nu oynadın"
# ---------------------------------------------------------------------------

async def get_streak(user_id: str) -> int:
    """Kullanıcının güncel Günün 5 Sorusu serisi (bugün oynamadıysa da geçerli).

    Dün ya da bugün oynanmışsa seri canlıdır; daha eskiyse KOPMUŞTUR → 0.
    """
    try:
        client = await get_redis()
        raw = await client.get(f"daily_challenge_streak:{user_id}")
        if not raw:
            return 0
        data = json.loads(raw)
        last = data.get("last_date")
        streak = int(data.get("streak", 0))
        today = await get_today_key()
        yesterday = (
            datetime.now(tz=_TRT_ZONE) - timedelta(days=1)
        ).strftime("%Y-%m-%d")
        if last in (today, yesterday):
            return streak
        return 0  # seri kopmuş
    except Exception as exc:
        logger.warning("daily_challenge get_streak failed for %s: %s", user_id, exc)
        return 0


async def bump_streak(user_id: str) -> int:
    """Bugün oynandığında seriyi güncelle ve YENİ seri değerini döndür.

    Dün oynanmışsa +1, bugün zaten işlenmişse aynı kalır, aksi halde 1'e döner.
    """
    today = await get_today_key()
    yesterday = (datetime.now(tz=_TRT_ZONE) - timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        client = await get_redis()
        key = f"daily_challenge_streak:{user_id}"
        raw = await client.get(key)
        data = json.loads(raw) if raw else {}
        last = data.get("last_date")
        streak = int(data.get("streak", 0))

        if last == today:
            new_streak = max(1, streak)  # bugün zaten sayılmış
        elif last == yesterday:
            new_streak = streak + 1
        else:
            new_streak = 1

        await client.set(
            key,
            json.dumps({"streak": new_streak, "last_date": today}),
            ex=_STREAK_TTL,
        )
        return new_streak
    except Exception as exc:
        logger.warning("daily_challenge bump_streak failed for %s: %s", user_id, exc)
        return 1


# ---------------------------------------------------------------------------
# Sonuç anlık görüntüsü — ana ekran kartı + paylaşım kartı bunu okur
# ---------------------------------------------------------------------------

async def save_result(user_id: str, result: dict) -> None:
    """Bugünün sonucunu sakla (48h) — oyuncu uygulamayı kapatsa da kart dolu kalır."""
    date_key = await get_today_key()
    try:
        client = await get_redis()
        await client.set(
            f"daily_challenge_result:{user_id}:{date_key}",
            json.dumps(result),
            ex=_RESULT_TTL,
        )
    except Exception as exc:
        logger.warning("daily_challenge save_result failed for %s: %s", user_id, exc)


async def get_result(user_id: str) -> dict | None:
    """Bugünün kayıtlı sonucunu döndür; oynanmadıysa/bulunamazsa None."""
    date_key = await get_today_key()
    try:
        client = await get_redis()
        raw = await client.get(f"daily_challenge_result:{user_id}:{date_key}")
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("daily_challenge get_result failed for %s: %s", user_id, exc)
        return None


async def get_rank_and_total(user_id: str) -> tuple[int, int]:
    """Bugünün sıralamasında (sıra, toplam oyuncu) ikilisi. Bulunamazsa (0, 0)."""
    date_key = await get_today_key()
    leaderboard_key = f"daily_challenge_score:{date_key}"
    try:
        client = await get_redis()
        rank_zero = await client.zrevrank(leaderboard_key, user_id)
        total = await client.zcard(leaderboard_key)
        rank = (rank_zero + 1) if rank_zero is not None else 0
        return rank, int(total or 0)
    except Exception as exc:
        logger.warning("daily_challenge get_rank_and_total failed for %s: %s", user_id, exc)
        return 0, 0


def percentile_for(rank: int, total: int) -> int:
    """"En iyi %X" değeri — 1. sıra → 1, sonuncu → 100. Veri yoksa 0."""
    if rank <= 0 or total <= 0:
        return 0
    return max(1, min(100, round(100 * rank / total)))


def build_share_text(results: list[bool], correct_count: int) -> str:
    """Wordle tarzı paylaşım metni — CEVAPLARI SIZDIRMAZ, sadece emoji ızgarası.

    Örnek:
        Bil ya da Düş — Günün 5 Sorusu
        🟩🟩🟥🟩🟥 4/5
        Sen kaç yaparsın?
    """
    grid = "".join("🟩" if ok else "🟥" for ok in results)
    return (
        "Bil ya da Düş — Günün 5 Sorusu\n"
        f"{grid} {correct_count}/{len(results)}\n"
        "Sen kaç yaparsın?"
    )


async def get_daily_leaderboard(limit: int = 100) -> list[dict]:
    """Return the top N players for today's daily challenge.

    Returns:
        List of dicts with keys: rank, user_id, score.
        Ordered by score descending (rank 1 = best).
    """
    date_key = await get_today_key()
    leaderboard_key = f"daily_challenge_score:{date_key}"
    try:
        client = await get_redis()
        # ZREVRANGE with scores, highest first
        entries = await client.zrevrange(leaderboard_key, 0, limit - 1, withscores=True)
        result = []
        for rank, (uid, score) in enumerate(entries, start=1):
            result.append({
                "rank": rank,
                "user_id": uid,
                "score": int(score),
            })
        return result
    except Exception as exc:
        logger.warning("daily_challenge get_daily_leaderboard failed: %s", exc)
        return []
