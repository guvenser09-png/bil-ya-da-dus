"""Uçtan uca oyun akışı testi: login → lobby → game → kazanan.

Gerçek bir oyuncu gibi davranır; 403 gitti mi, sorular geliyor mu,
tur/eleme/kazanan akışı çalışıyor mu kanıtlar.

Çalıştırma:
  cd backend && uv run python scripts/e2e_game_test.py
"""
import asyncio
import json
import urllib.request

import websockets

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"
USER = {"username_or_email": "testoyuncu", "password": "sifre1234"}


def login() -> str:
    req = urllib.request.Request(
        f"{BASE}/api/auth/login",
        data=json.dumps(USER).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=10) as r:
        return json.loads(r.read())["access_token"]


async def run():
    token = login()
    print("✓ Login OK, token alındı")

    # --- LOBBY ---
    game_id = None
    async with websockets.connect(f"{WS}/ws/lobby?token={token}") as lobby:
        await lobby.send(json.dumps({
            "action": "join", "username": "testoyuncu",
            "display_name": "Test", "avatar_id": "robot",
        }))
        print("→ Lobiye katılındı, oyun başlamasını bekliyorum (≤30s)...")
        while True:
            msg = json.loads(await asyncio.wait_for(lobby.recv(), timeout=35))
            t = msg.get("type")
            if t == "lobby_joined":
                print(f"  lobi: {msg.get('countdown_seconds')}s geri sayım, {len(msg.get('players', []))} oyuncu")
            elif t == "game_starting":
                game_id = msg["game_id"]
                print(f"✓ OYUN BAŞLIYOR — game_id={game_id[:8]} (oyuncu={msg.get('total_players')}, bot={msg.get('bot_count')})")
                break

    # --- GAME ---
    rounds_seen = 0
    async with websockets.connect(f"{WS}/ws/game/{game_id}?token={token}") as game:
        print("✓ Oyun WS bağlandı — 403 YOK ✅")
        while True:
            try:
                msg = json.loads(await asyncio.wait_for(game.recv(), timeout=40))
            except asyncio.TimeoutError:
                print("✗ Zaman aşımı (mesaj gelmedi)")
                break
            t = msg.get("type")
            if t == "round_start":
                rounds_seen += 1
                q = msg.get("question") or msg
                soru = q.get("question") or q.get("content") or "?"
                tip = q.get("tip") or q.get("type") or "?"
                print(f"  TUR {msg.get('round') or msg.get('current_round') or rounds_seen} [{tip}]: {str(soru)[:60]}")
                # Bir cevap gönder (tahmin için sayı, diğerleri için 0)
                ans = 0
                if tip == "tahmin":
                    ans = (q.get("min_value", 0) + q.get("max_value", 100)) // 2
                try:
                    await game.send(json.dumps({"type": "submit_answer", "answer": ans, "time_remaining": 5.0}))
                except Exception:
                    pass
            elif t == "round_reveal":
                elim = msg.get("eliminated", [])
                alive = msg.get("alive_count")
                if alive is None:
                    st = msg.get("state", {})
                    alive = st.get("alive_count")
                print(f"  ↳ TUR SONU: doğru={msg.get('correct_answer')}, elenen={elim}, kalan={alive}")
                # Oyuncunun KENDİ sonucunu yazdır — cevabının kaydedildiğinin kanıtı
                results = msg.get("results") or msg.get("player_results") or {}
                mine = results.get("testoyuncu")
                if mine is not None:
                    print(f"     >>> testoyuncu: cevap={mine.get('answer')} "
                          f"correct={mine.get('correct')} score={mine.get('score')} "
                          f"total={mine.get('total_score')}")
                else:
                    print("     >>> testoyuncu: results'ta KAYIT YOK (cevap kaydedilmedi!)")
            elif t == "game_state":
                pass
            elif t == "spectator_mode":
                print("  (elendim → izleyici, oyunu izlemeye devam)")
            elif t == "game_finished":
                w = msg.get("winner")
                wname = w.get("username") if isinstance(w, dict) else w
                standings = msg.get("final_standings", [])
                print(f"✓ OYUN BİTTİ — KAZANAN: {wname}")
                print(f"  Sıralama (ilk 3): {[(s.get('username'), s.get('score'), s.get('is_winner')) for s in standings[:3]]}")
                return True
    return False


if __name__ == "__main__":
    ok = asyncio.run(run())
    print("\n=== SONUÇ:", "BAŞARILI ✅" if ok else "TAMAMLANMADI ✗", "===")
