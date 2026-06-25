"""Doğru cevap veren e2e: her tur DB'den doğru cevabı bulup gönderir.

Amaç: "doğru bilmeme rağmen elendin" hatasını kesin teşhis etmek. Oyuncu
HER turu DOĞRU cevaplarsa son tura kadar hayatta kalmalı.

Çalıştırma: cd backend && uv run python scripts/e2e_correct_test.py
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


async def run():
    token = login()
    print("✓ Login OK")
    game_id = None
    async with websockets.connect(f"{WS}/ws/lobby?token={token}") as lobby:
        await lobby.send(json.dumps({"action": "join", "username": ME, "display_name": "Test", "avatar_id": "robot"}))
        while True:
            msg = json.loads(await asyncio.wait_for(lobby.recv(), timeout=40))
            if msg.get("type") == "game_starting":
                game_id = msg["game_id"]
                print(f"✓ OYUN BAŞLIYOR game_id={game_id[:8]}")
                break

    eliminated_me = False
    print("⏳ Yavaş geçiş simülasyonu: oyun WS bağlantısı 6sn gecikiyor...")
    await asyncio.sleep(6)
    async with websockets.connect(f"{WS}/ws/game/{game_id}?token={token}") as game:
        print("✓ Oyun WS bağlandı")
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=40))
            except asyncio.TimeoutError:
                print("✗ timeout"); break
            t = msg.get("type")
            if t == "round_start":
                q = msg.get("question") or msg
                qid = q.get("id")
                content = q.get("content") or q.get("question")
                rnd = msg.get("round") or msg.get("current_round")
                ans, qtype = await correct_for(qid, content)
                print(f"  TUR {rnd} [{qtype}] doğru cevap={ans} → gönderiliyor (istemci protokolü)")
                if ans is not None:
                    # GERÇEK İSTEMCİ PROTOKOLÜ: tahmin=submit(double)+lock, diğerleri=sadece submit
                    if qtype == "tahmin":
                        await game.send(json.dumps({"type": "submit_answer", "answer": float(ans), "time_remaining": 4.0}))
                        await game.send(json.dumps({"type": "lock_answer"}))
                    else:
                        await game.send(json.dumps({"type": "submit_answer", "answer": ans, "time_remaining": 4.0}))
            elif t == "round_reveal":
                results = msg.get("results") or {}
                mine = results.get(ME)
                elim = msg.get("eliminated", [])
                if ME in elim:
                    eliminated_me = True
                tag = ""
                if mine is not None:
                    tag = f"correct={mine.get('correct')} score={mine.get('score')}"
                print(f"    ↳ {ME}: {tag} {'❌ELENDİM' if ME in elim else '✅ hayatta'}")
            elif t == "game_finished":
                w = msg.get("winner")
                wname = w.get("username") if isinstance(w, dict) else w
                print(f"✓ OYUN BİTTİ kazanan={wname} | ben_elendim={eliminated_me}")
                return not eliminated_me
    return False


if __name__ == "__main__":
    ok = asyncio.run(run())
    print("\n=== Doğru cevaplara rağmen hayatta kaldım mı:", "EVET ✅ (backend doğru)" if ok else "HAYIR ❌ (BACKEND HATASI bulundu)", "===")
