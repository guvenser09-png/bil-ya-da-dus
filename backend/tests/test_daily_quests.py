"""Günün 5 Sorusu ödülü + Günlük 3 Görev testleri.

Kapsam:
- Günün 5 Sorusu: coin ödül formülü, günde BİR kez (idempotent), paylaşım
  kartı payload'ı (🟩🟥 ızgarası + cevap sızdırmama), sıra/yüzde.
- Görevler: deterministik seçim, maç sonu ilerleme, claim idempotency.
"""

import json

import pytest
from httpx import AsyncClient


# ---------------------------------------------------------------------------
# Sahte Redis — daily_challenge_service/quest_service'in ihtiyaç duyduğu
# komutları (SET NX, ZADD, ZREVRANK, ZCARD) gerçekçi semantikle taklit eder.
# ---------------------------------------------------------------------------

class FakeRedis:
    def __init__(self):
        self.store: dict = {}

    async def get(self, key):
        return self.store.get(key)

    async def set(self, key, value, ex=None, nx=False):
        if nx and key in self.store:
            return None  # gerçek Redis SET NX: yazma, None dön
        self.store[key] = value
        return True

    async def exists(self, key):
        return 1 if key in self.store else 0

    async def expire(self, key, seconds):
        return True

    async def zadd(self, key, mapping):
        z = self.store.setdefault(key, {})
        z.update(mapping)

    async def zrevrank(self, key, member):
        z = self.store.get(key) or {}
        if member not in z:
            return None
        ordered = sorted(z.items(), key=lambda kv: kv[1], reverse=True)
        return [m for m, _ in ordered].index(member)

    async def zcard(self, key):
        return len(self.store.get(key) or {})


@pytest.fixture
def fake_redis(monkeypatch):
    """daily_challenge_service + quest_service'in get_redis'ini sahte Redis'e bağla.

    Not: iki servis de `from app.redis_client import get_redis` ile ismi kendi
    modülüne bağladığı için conftest'in app.redis_client yamaları buraya
    ULAŞMAZ — modül düzeyinde yamamak ŞART.
    """
    from app.services import daily_challenge_service, quest_service

    r = FakeRedis()

    async def _get_redis():
        return r

    monkeypatch.setattr(daily_challenge_service, "get_redis", _get_redis)
    monkeypatch.setattr(quest_service, "get_redis", _get_redis)
    return r


async def _register(client: AsyncClient, username: str) -> str:
    res = await client.post("/api/auth/register", json={
        "username": username,
        "password": "test123abc",
        "email": f"{username}@example.com",
    })
    return res.json()["access_token"]


async def _coins(client: AsyncClient, token: str) -> int:
    res = await client.get("/api/users/me", headers={"Authorization": f"Bearer {token}"})
    return int(res.json()["coins"])


# Günün sabit 5 sorusuna TAM DOĞRU cevap dizisi (fallback soru seti):
# [dogru_yanlis=0, gorsel=0, karsilastirma=0, coktan_secmeli=1, tahmin=85]
ALL_CORRECT = [0, 0, 0, 1, 85]


# ---------------------------------------------------------------------------
# 1) Günün 5 Sorusu — ödül formülü
# ---------------------------------------------------------------------------

def test_daily_reward_formula():
    """Taban 100 + doğru başına 20; 5/5 = 200 (üst sınır)."""
    from app.services.daily_challenge_service import (
        DAILY_CHALLENGE_MAX_REWARD,
        reward_for_correct_count,
    )

    assert reward_for_correct_count(0) == 100
    assert reward_for_correct_count(3) == 160
    assert reward_for_correct_count(5) == 200
    assert DAILY_CHALLENGE_MAX_REWARD == 200
    # Bozuk girdi üst sınırı aşamaz (savunmacı).
    assert reward_for_correct_count(99) == 200


# ---------------------------------------------------------------------------
# 2) Cevap değerlendirme — sunucu tarafı (istemci "5/5 yaptım" diyemez)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_grade_answers_and_estimate_tolerance():
    """grade_answers doğru/yanlış dizisi üretir; tahmin turunda %10 tolerans."""
    from app.services.daily_challenge_service import (
        _get_fallback_questions,
        grade_answers,
    )

    questions = _get_fallback_questions()

    assert grade_answers(questions, ALL_CORRECT) == [True] * 5

    # 4. soru yanlış (doğru: 1), 5. soru tolerans dışında (85 ± 7 bandı).
    mixed = grade_answers(questions, [0, 0, 0, 3, 120])
    assert mixed == [True, True, True, False, False]

    # Tahmin 88 → |88-85| = 3 <= 0.10 * (120-50) = 7 → DOĞRU sayılır.
    assert grade_answers(questions, [0, 0, 0, 1, 88])[4] is True

    # Eksik/None cevaplar yanlış sayılır, patlamaz.
    assert grade_answers(questions, [None, 0]) == [False, True, False, False, False]


# ---------------------------------------------------------------------------
# 3) Paylaşım kartı payload'ı — emoji ızgarası, cevap SIZDIRMAZ
# ---------------------------------------------------------------------------

def test_share_text_payload():
    """Wordle tarzı metin: ızgara + skor + kanca. Soru/cevap metni İÇERMEZ."""
    from app.services.daily_challenge_service import build_share_text

    text = build_share_text([True, True, False, True, False], 3)

    assert text.splitlines()[0] == "Bil ya da Düş — Günün 5 Sorusu"
    assert "🟩🟩🟥🟩🟥 3/5" in text
    assert "Sen kaç yaparsın?" in text
    # Cevap sızıntısı yok: soru metinlerinden hiçbiri paylaşımda geçmiyor.
    assert "İstanbul" not in text and "Türkçe" not in text


def test_percentile_for():
    """Sıra + toplam → "en iyi %X" (1. sıra en iyi, veri yoksa 0)."""
    from app.services.daily_challenge_service import percentile_for

    assert percentile_for(1, 100) == 1
    assert percentile_for(50, 100) == 50
    assert percentile_for(100, 100) == 100
    assert percentile_for(0, 0) == 0


# ---------------------------------------------------------------------------
# 4) Uç: skor gönderimi → coin + payload; günde BİR kez (idempotent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_daily_challenge_submit_grants_coins_once(client: AsyncClient, fake_redis):
    """5/5 → +200 altın, paylaşım metni ve sıra döner; İKİNCİ gönderim 403 (coin YOK)."""
    token = await _register(client, "dailyhero")
    headers = {"Authorization": f"Bearer {token}"}
    before = await _coins(client, token)

    res = await client.post(
        "/api/games/daily-challenge/score",
        headers=headers,
        json={"score": 120, "answers": ALL_CORRECT},
    )
    assert res.status_code == 200
    data = res.json()

    assert data["correct_count"] == 5
    assert data["results"] == [True] * 5
    assert data["coins_earned"] == 200
    assert data["rank"] == 1
    assert data["total_players"] == 1
    assert data["percentile"] == 100  # tek oyuncu → hem 1. hem sonuncu
    assert data["streak"] == 1
    assert "🟩🟩🟩🟩🟩 5/5" in data["share_text"]
    assert await _coins(client, token) == before + 200

    # İkinci gönderim: hak zaten kullanıldı → 403, bakiye DEĞİŞMEZ.
    dup = await client.post(
        "/api/games/daily-challenge/score",
        headers=headers,
        json={"score": 999, "answers": ALL_CORRECT},
    )
    assert dup.status_code == 403
    assert await _coins(client, token) == before + 200

    # Sorular da bir daha verilmez.
    assert (await client.get("/api/games/daily-challenge", headers=headers)).status_code == 403


@pytest.mark.asyncio
async def test_daily_challenge_status_reflects_result(client: AsyncClient, fake_redis):
    """/status: oynamadan önce boş, oynadıktan sonra sonucu + seriyi taşır."""
    token = await _register(client, "dailystatus")
    headers = {"Authorization": f"Bearer {token}"}

    before = (await client.get("/api/games/daily-challenge/status", headers=headers)).json()
    assert before["played_today"] is False
    assert before["streak"] == 0
    assert before["result"] is None
    assert before["max_reward"] == 200

    await client.post(
        "/api/games/daily-challenge/score",
        headers=headers,
        json={"score": 40, "answers": [0, 0, 0, 3, 120]},  # 3/5
    )

    after = (await client.get("/api/games/daily-challenge/status", headers=headers)).json()
    assert after["played_today"] is True
    assert after["streak"] == 1
    assert after["result"]["correct_count"] == 3
    assert after["result"]["coins_earned"] == 160
    assert after["result"]["results"] == [True, True, True, False, False]
    assert "🟩🟩🟩🟥🟥 3/5" in after["result"]["share_text"]


# ---------------------------------------------------------------------------
# 5) Görevler — deterministik seçim + maç sonu ilerleme
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quests_today_deterministic_and_progress(client: AsyncClient, fake_redis):
    """Aynı gün aynı 3 görev; maç sonu kancası ilerlemeyi artırır."""
    from app.services import quest_service

    token = await _register(client, "questplayer")
    headers = {"Authorization": f"Bearer {token}"}

    res = await client.get("/api/quests/today", headers=headers)
    assert res.status_code == 200
    data = res.json()
    assert len(data["quests"]) == 3
    assert all(q["progress"] == 0 and not q["completed"] for q in data["quests"])

    # Seçim deterministik: ikinci çağrı AYNI görevleri döner.
    again = (await client.get("/api/quests/today", headers=headers)).json()
    assert [q["id"] for q in again["quests"]] == [q["id"] for q in data["quests"]]

    # user_id'yi token'dan değil, /users/me'den al.
    me = (await client.get("/api/users/me", headers=headers)).json()
    user_id = me["id"]

    # Maç sonu: kazandı, 4 doğru, finale kaldı → tüm maç görevleri ilerler.
    await quest_service.record_match_end(
        user_id, won=True, correct_answers=4, reached_final=True
    )

    after = (await client.get("/api/quests/today", headers=headers)).json()
    by_id = {q["id"]: q for q in after["quests"]}
    for qid, q in by_id.items():
        if qid == "play_3_matches":
            assert q["progress"] == 1 and not q["completed"]
        elif qid == "answer_correct_10":
            assert q["progress"] == 4 and not q["completed"]  # 4 doğru, hedef 10
        else:
            assert q["completed"] is True and q["claimable"] is True

    # "3 maç oyna" ancak 3. maçta tamamlanır (üst sınırı aşmaz).
    if "play_3_matches" in by_id:
        for _ in range(4):
            await quest_service.record_match_end(
                user_id, won=False, correct_answers=0, reached_final=False
            )
        final = (await client.get("/api/quests/today", headers=headers)).json()
        q3 = next(q for q in final["quests"] if q["id"] == "play_3_matches")
        assert q3["progress"] == 3 and q3["completed"] is True


@pytest.mark.asyncio
async def test_answer_correct_quest_progress_by_matches(client: AsyncClient, fake_redis):
    """Gün içi doğru cevaplar toplanır; 10'a ulaşınca 'answer_correct_10' tamamlanır."""
    from app.services import quest_service

    token = await _register(client, "questcorrect")
    headers = {"Authorization": f"Bearer {token}"}
    me = (await client.get("/api/users/me", headers=headers)).json()
    user_id = me["id"]

    # Bu görevin bugün aktif olduğu bir gün seçilmeyebilir → aktif değilse
    # yabancı görev sızmadığını doğrula.
    date_key = quest_service.today_key()
    active_ids = {q["id"] for q in quest_service.pick_quests(user_id, date_key)}

    # İki maçta 6 + 4 = 10 doğru → kümülatif hedef (10) tamamlanır.
    await quest_service.record_match_end(
        user_id, won=False, correct_answers=6, reached_final=False
    )
    await quest_service.record_match_end(
        user_id, won=False, correct_answers=4, reached_final=False
    )

    quests = (await client.get("/api/quests/today", headers=headers)).json()["quests"]
    if "answer_correct_10" in active_ids:
        q = next(q for q in quests if q["id"] == "answer_correct_10")
        assert q["progress"] == 10 and q["completed"] is True and q["claimable"] is True
    else:
        raw = fake_redis.store.get(f"quests:{user_id}:{date_key}")
        progress = json.loads(raw)["progress"] if raw else {}
        assert "answer_correct_10" not in progress


@pytest.mark.asyncio
async def test_record_daily_challenge_is_noop(client: AsyncClient, fake_redis):
    """record_daily_challenge artık no-op: çağrı patlamaz, hiçbir görevi ilerletmez."""
    from app.services import quest_service

    token = await _register(client, "questnoop")
    headers = {"Authorization": f"Bearer {token}"}
    user_id = (await client.get("/api/users/me", headers=headers)).json()["id"]

    # Çağrı hata vermez ve Redis'e hiçbir görev durumu yazmaz.
    await quest_service.record_daily_challenge(user_id)

    date_key = quest_service.today_key()
    assert fake_redis.store.get(f"quests:{user_id}:{date_key}") is None


# ---------------------------------------------------------------------------
# 6) Görev ödülü — tamamlanmadan alınamaz, iki kez alınamaz (idempotent)
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_quest_claim_idempotent(client: AsyncClient, fake_redis):
    """AL: tamamlanmadan reddedilir; bir kez altın verir; ikinci kez vermez."""
    from app.services import quest_service

    token = await _register(client, "questclaim")
    headers = {"Authorization": f"Bearer {token}"}
    me = (await client.get("/api/users/me", headers=headers)).json()
    user_id = me["id"]
    before = await _coins(client, token)

    quests = (await client.get("/api/quests/today", headers=headers)).json()["quests"]
    target = quests[0]

    # 1) Tamamlanmadan claim → altın YOK.
    early = await client.post(f"/api/quests/{target['id']}/claim", headers=headers)
    assert early.status_code == 200
    assert early.json()["claimed"] is False
    assert early.json()["reason"] == "not_completed"
    assert await _coins(client, token) == before

    # 2) Görevi tamamla (hangi görev olursa olsun hedefe ulaştır).
    for _ in range(3):
        await quest_service.record_match_end(
            user_id, won=True, correct_answers=5, reached_final=True
        )
    await quest_service.record_daily_challenge(user_id)

    ok = await client.post(f"/api/quests/{target['id']}/claim", headers=headers)
    assert ok.status_code == 200
    assert ok.json()["claimed"] is True
    assert ok.json()["reward"] == target["reward"]
    assert await _coins(client, token) == before + target["reward"]

    # 3) Aynı görev ikinci kez → çift ödül YOK.
    dup = await client.post(f"/api/quests/{target['id']}/claim", headers=headers)
    assert dup.status_code == 200
    assert dup.json()["claimed"] is False
    assert dup.json()["reason"] == "already_claimed"
    assert await _coins(client, token) == before + target["reward"]

    # 4) Bugün aktif olmayan bir görev id'si → 404.
    unknown = await client.post("/api/quests/bogus_quest/claim", headers=headers)
    assert unknown.status_code == 404
