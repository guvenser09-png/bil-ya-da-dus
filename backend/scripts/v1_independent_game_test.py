"""DOĞRULAYICI AJAN 1 — bağımsız tam oyun testi.

Tek gerçek oyuncu (testoyuncu) ile tam bir oyun oynar. Oyun WS'inden gelen
TÜM mesajları sayar ve şunları KANITLAR:
  1. game_finished mesajı TAM 1 kez geldi (≥2 ise BUG).
  2. game_id taşıması gereken her mesajda game_id var ve hep aynı.
  3. Oyun en az birkaç tur sürüyor; 2. turda erken bitmiyor (doğru cevaplayan
     oyuncu için). round_start sayısı >= 3 beklenir.

Bu test, game_finished'i ilk gördükten sonra WS'i KAPATMAZ; ekstra mükerrer
game_finished gelir mi diye 8 saniye daha dinler (kişisel + broadcast çifti
yakalanır).

Çalıştırma: cd backend && uv run python scripts/v1_independent_game_test.py
"""
import asyncio
import json
import os
import sys
import urllib.request
from collections import Counter

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets
from sqlalchemy import select

from app.database import async_session_factory
from app.models.question import Question

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"
USER = {"username_or_email": "testoyuncu", "password": "sifre1234"}
ME = "testoyuncu"

GAME_ID_TYPES = {
    "round_start", "round_reveal", "round_transition",
    "game_finished", "game_state", "game_started", "spectator_mode",
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


async def run() -> bool:
    token = login()
    print("✓ Login OK")
    game_id = await get_game_id(token)
    print(f"✓ OYUN BAŞLIYOR game_id={game_id}")

    msg_counter: Counter = Counter()
    finished_count = 0
    round_start_count = 0
    missing_game_id = []
    wrong_game_id = []
    finished_after_round = None  # game_finished hangi turdan sonra geldi

    async with websockets.connect(f"{WS}/ws/game/{game_id}?token={token}") as game:
        print("✓ Oyun WS bağlandı, TÜM mesajlar sayılıyor...")
        listening_after_finish = False
        while True:
            timeout = 8 if listening_after_finish else 45
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=timeout))
            except asyncio.TimeoutError:
                if listening_after_finish:
                    break  # ekstra dinleme bitti, mükerrer gelmedi
                print("✗ TIMEOUT (oyun mesajı gelmedi)")
                break

            t = msg.get("type", "?")
            msg_counter[t] += 1

            # game_id doğrulaması
            if t in GAME_ID_TYPES:
                if "game_id" not in msg:
                    missing_game_id.append(t)
                elif msg["game_id"] != game_id:
                    wrong_game_id.append(f"{t}={msg.get('game_id')}")

            if t == "round_start":
                round_start_count += 1
                q = msg.get("question") or msg
                ans, qtype = await correct_for(q.get("id"), q.get("content") or q.get("question"))
                rnd = msg.get("round") or msg.get("current_round")
                print(f"  TUR {rnd} [{qtype}] (round_start #{round_start_count}) cevap={ans}")
                if ans is not None:
                    if qtype == "tahmin":
                        await game.send(json.dumps({"type": "submit_answer", "answer": float(ans), "time_remaining": 4.0}))
                        await game.send(json.dumps({"type": "lock_answer"}))
                    else:
                        await game.send(json.dumps({"type": "submit_answer", "answer": ans, "time_remaining": 4.0}))
            elif t == "round_reveal":
                results = msg.get("results") or {}
                mine = results.get(ME)
                if mine is not None:
                    print(f"    ↳ reveal: correct={mine.get('correct')} score={mine.get('score')}")
            elif t == "game_finished":
                finished_count += 1
                if finished_after_round is None:
                    finished_after_round = round_start_count
                w = msg.get("winner")
                wname = w.get("username") if isinstance(w, dict) else w
                print(f"  ↳ game_finished #{finished_count} kazanan={wname} (tur {round_start_count} sonrası)")
                listening_after_finish = True  # mükerrer var mı diye dinlemeye devam

    print("\n--- MESAJ SAYIMI ---")
    for k, v in sorted(msg_counter.items()):
        print(f"  {k}: {v}")

    ok = True
    print("\n--- KANIT ---")
    # 1) game_finished tam 1
    if finished_count == 1:
        print(f"✓ [1] game_finished TAM 1 kez geldi")
    else:
        print(f"✗ [1] game_finished {finished_count} kez geldi (beklenen 1) → BUG")
        ok = False
    # 2) game_id
    if missing_game_id:
        print(f"✗ [2] game_id EKSİK olan mesaj tipleri: {set(missing_game_id)}")
        ok = False
    elif wrong_game_id:
        print(f"✗ [2] YANLIŞ game_id taşıyan mesajlar: {wrong_game_id}")
        ok = False
    else:
        print(f"✓ [2] game_id taşıması gereken tüm mesajlarda mevcut ve tümü = {game_id[:8]}")
    # 3) erken bitmeme
    if round_start_count >= 3 and (finished_after_round is None or finished_after_round >= 3):
        print(f"✓ [3] Oyun {round_start_count} tur sürdü, 2. turda erken bitmedi")
    else:
        print(f"✗ [3] Oyun erken bitti: round_start={round_start_count}, finish_after_round={finished_after_round}")
        ok = False

    return ok


if __name__ == "__main__":
    ok = asyncio.run(run())
    print("\n=== BAĞIMSIZ TAM OYUN TESTİ:", "GEÇTİ ✅" if ok else "KALDI ❌", "===")
    sys.exit(0 if ok else 1)
