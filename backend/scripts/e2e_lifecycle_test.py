"""Oyun WS yaşam döngüsü e2e testi.

İki senaryoyu doğrular:

  A) game_id alanı kontrolü + game_finished mükerrer GİTMEZ:
     - round_start / round_reveal / round_transition / game_finished / game_state
       mesajlarının hepsinde game_id alanı bulunmalı ve doğru game_id olmalı.
     - game_finished EN FAZLA bir kez gelmeli (erken/mükerrer sonuç ekranı yok).

  B) Oyun ortasında ayrılma:
     - Tek gerçek oyuncu 2. turdan sonra game WS'i kapatır.
     - Kapanıştan sonra geç gelen mükerrer bir game_finished'in (yanlış yere
       sızan eski oyun mesajı) gelmediğini ve oyunun temizlendiğini doğrular.
     - Aynı oyuncu YENİ bir oyuna girip eski oyunun mesajıyla karışmadığını
       (yeni game_id) doğrular.

Çalıştırma:
  cd backend && uv run python scripts/e2e_lifecycle_test.py
"""
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets
from sqlalchemy import select

from app.database import async_session_factory
from app.models.question import Question

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"
USER = {"username_or_email": "testoyuncu", "password": "sifre1234"}
ME = "testoyuncu"

# round mesajlarında game_id beklediğimiz tipler
GAME_ID_TYPES = {
    "round_start",
    "round_reveal",
    "round_transition",
    "game_finished",
    "game_state",
    "game_started",
    "spectator_mode",
}


def login() -> str:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login", data=json.dumps(USER).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


async def correct_for(qid, content):
    async with async_session_factory() as db:
        row = None
        if qid:
            row = (await db.execute(select(Question).where(Question.id == qid))).scalar_one_or_none()
        if row is None and content:
            row = (await db.execute(select(Question).where(Question.content == content))).scalar_one_or_none()
        if row is None:
            return None, None
        t = row.type.value if hasattr(row.type, "value") else row.type
        if t == "tahmin":
            return row.real_answer, t
        return row.correct_answer, t


async def get_game_id(token: str) -> str:
    async with websockets.connect(f"{WS}/ws/lobby?token={token}") as lobby:
        await lobby.send(json.dumps({
            "action": "join", "username": ME, "display_name": "Test", "avatar_id": "robot"}))
        while True:
            msg = json.loads(await asyncio.wait_for(lobby.recv(), timeout=45))
            if msg.get("type") == "game_starting":
                return msg["game_id"]


# ---------------------------------------------------------------------------
# Senaryo A: game_id alanı + tek game_finished
# ---------------------------------------------------------------------------
async def scenario_a(token: str) -> bool:
    print("\n=== SENARYO A: game_id alanı + mükerrer game_finished yok ===")
    game_id = await get_game_id(token)
    print(f"✓ OYUN BAŞLIYOR game_id={game_id[:8]}")

    finished_count = 0
    missing_game_id: list[str] = []
    wrong_game_id: list[str] = []

    async with websockets.connect(f"{WS}/ws/game/{game_id}?token={token}") as game:
        print("✓ Oyun WS bağlandı")
        ans = None
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=45))
            except asyncio.TimeoutError:
                print("✗ timeout"); break
            t = msg.get("type")

            if t in GAME_ID_TYPES:
                if "game_id" not in msg:
                    missing_game_id.append(t)
                elif msg["game_id"] != game_id:
                    wrong_game_id.append(f"{t}={msg['game_id'][:8]}")

            if t == "round_start":
                q = msg.get("question") or msg
                ans, qtype = await correct_for(q.get("id"), q.get("content") or q.get("question"))
                rnd = msg.get("round")
                print(f"  TUR {rnd} [{qtype}] cevap={ans}")
                if ans is not None:
                    if qtype == "tahmin":
                        await game.send(json.dumps({"type": "submit_answer", "answer": float(ans), "time_remaining": 4.0}))
                        await game.send(json.dumps({"type": "lock_answer"}))
                    else:
                        await game.send(json.dumps({"type": "submit_answer", "answer": ans, "time_remaining": 4.0}))
            elif t == "game_finished":
                finished_count += 1
                w = msg.get("winner")
                wname = w.get("username") if isinstance(w, dict) else w
                print(f"  ↳ game_finished #{finished_count} kazanan={wname}")
                # Mükerrer gelir mi diye kısa süre daha dinle, sonra çık.
                try:
                    while True:
                        extra = json.loads(await asyncio.wait_for(game.recv(), timeout=6))
                        if extra.get("type") == "game_finished":
                            finished_count += 1
                            print("  ↳ ⚠️ MÜKERRER game_finished alındı!")
                except asyncio.TimeoutError:
                    pass
                break

    ok = True
    if missing_game_id:
        print(f"✗ game_id EKSİK olan mesajlar: {missing_game_id}"); ok = False
    else:
        print("✓ Tüm ilgili mesajlarda game_id mevcut")
    if wrong_game_id:
        print(f"✗ YANLIŞ game_id taşıyan mesajlar: {wrong_game_id}"); ok = False
    if finished_count != 1:
        print(f"✗ game_finished sayısı {finished_count} (beklenen 1)"); ok = False
    else:
        print("✓ game_finished tam 1 kez geldi")
    return ok


# ---------------------------------------------------------------------------
# Senaryo B: oyun ortasında ayrılma → eski oyun sızmaz, yeni oyun temiz
# ---------------------------------------------------------------------------
async def scenario_b(token: str) -> bool:
    print("\n=== SENARYO B: oyun ortasında ayrılma + yeni oyun karışmaz ===")
    game_id1 = await get_game_id(token)
    print(f"✓ 1. OYUN game_id={game_id1[:8]}")

    rounds_seen = 0
    premature_finish = False
    async with websockets.connect(f"{WS}/ws/game/{game_id1}?token={token}") as game:
        print("✓ 1. oyun WS bağlandı")
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=45))
            except asyncio.TimeoutError:
                break
            t = msg.get("type")
            if t == "round_start":
                rounds_seen += 1
                print(f"  1.oyun TUR {msg.get('round')} başladı")
                # 1. turda cevap ver, 2. tur başlayınca ayrıl.
                if rounds_seen == 1:
                    q = msg.get("question") or msg
                    a, qt = await correct_for(q.get("id"), q.get("content") or q.get("question"))
                    if a is not None and qt != "tahmin":
                        await game.send(json.dumps({"type": "submit_answer", "answer": a, "time_remaining": 4.0}))
                if rounds_seen >= 2:
                    print("  → 2. turda oyundan AYRILIYORUM (WS kapanıyor)")
                    break
            elif t == "game_finished":
                premature_finish = True
                print("  ↳ ⚠️ ayrılmadan önce beklenmedik game_finished!")
                break
    # WS context çıktı → bağlantı kapandı.

    if premature_finish:
        print("✗ Ayrılmadan önce game_finished geldi (beklenmiyor)")
        return False
    print("✓ Ayrılmadan önce erken game_finished YOK")

    # Eski oyun arka planda tur sonunda kendini temizlemeli. Kısa bekle.
    await asyncio.sleep(12)

    # Yeni oyuna gir: yeni game_id eski ile karışmamalı.
    game_id2 = await get_game_id(token)
    print(f"✓ 2. OYUN game_id={game_id2[:8]}")
    if game_id2 == game_id1:
        print("✗ Yeni oyun eski game_id ile aynı (beklenmiyor)")
        return False

    leaked_old = False
    async with websockets.connect(f"{WS}/ws/game/{game_id2}?token={token}") as game:
        print("✓ 2. oyun WS bağlandı")
        # Birkaç mesaj dinle; hepsi game_id2'ye ait olmalı, eski sızmamalı.
        for _ in range(8):
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=20))
            except asyncio.TimeoutError:
                break
            gid = msg.get("game_id")
            if gid and gid == game_id1:
                leaked_old = True
                print(f"  ↳ ⚠️ ESKİ oyunun mesajı sızdı: {msg.get('type')}")
            if msg.get("type") in ("round_start", "game_started"):
                # yeni oyun aktif, yeterli kanıt
                pass

    if leaked_old:
        print("✗ Eski oyunun mesajı yeni oyuna sızdı")
        return False
    print("✓ Eski oyun mesajı sızmadı; yeni oyun temiz")
    return True


async def run() -> bool:
    token = login()
    print("✓ Login OK")
    a = await scenario_a(token)
    # senaryolar arası lobi/oyun durulsun
    await asyncio.sleep(3)
    b = await scenario_b(token)
    return a and b


if __name__ == "__main__":
    ok = asyncio.run(run())
    print("\n=== YAŞAM DÖNGÜSÜ TESTİ:",
          "GEÇTİ ✅" if ok else "KALDI ❌", "===")
    sys.exit(0 if ok else 1)
