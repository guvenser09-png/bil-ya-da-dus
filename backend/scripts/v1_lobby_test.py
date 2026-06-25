"""DOĞRULAYICI AJAN 1 — bağımsız lobi testi.

Tek gerçek oyuncu (testoyuncu) lobiye join olur. Lobi WS'inden gelen TÜM
mesajları izleyip şunları KANITLAR:

  1. Katılan oyuncu KENDİ player_joined'ını ALMIYOR (kendi user_id'siyle
     player_joined gelmemeli; ayrıca lobby_joined geldikten sonra ilk
     player_joined zaten bot olmalı).
  2. Hiçbir mesajdaki player_count / total_count 20'yi GEÇMİYOR (max 20).
  3. game_starting total_players=20 ile geliyor (lobi tam dolu başlıyor).

Çalıştırma: cd backend && uv run python scripts/v1_lobby_test.py
"""
import asyncio
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import websockets

BASE = "http://localhost:8000"
WS = "ws://localhost:8000"
USER = {"username_or_email": "testoyuncu", "password": "sifre1234"}
ME = "testoyuncu"
MAX_PLAYERS = 20


def login():
    req = urllib.request.Request(
        f"{BASE}/api/auth/login", data=json.dumps(USER).encode(),
        headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=10) as r:
        body = json.loads(r.read())
        return body["access_token"]


async def run() -> bool:
    token = login()
    print("✓ Login OK")

    my_user_id = None
    saw_self_player_joined = False
    max_count_seen = 0
    over_limit_msgs = []
    game_starting_total = None
    player_joined_count = 0

    async with websockets.connect(f"{WS}/ws/lobby?token={token}") as lobby:
        # connected handshake (kendi user_id'mizi öğrenelim)
        first = json.loads(await asyncio.wait_for(lobby.recv(), timeout=10))
        if first.get("type") == "connected":
            my_user_id = first.get("user_id")
            print(f"✓ connected, my_user_id={my_user_id}")

        await lobby.send(json.dumps({
            "action": "join", "username": ME, "display_name": "Test", "avatar_id": "robot"}))

        while True:
            try:
                msg = json.loads(await asyncio.wait_for(lobby.recv(), timeout=45))
            except asyncio.TimeoutError:
                print("✗ TIMEOUT — game_starting gelmedi")
                break
            t = msg.get("type")

            # sayı alanlarını topla
            for field in ("player_count", "total_players"):
                if field in msg and isinstance(msg[field], int):
                    max_count_seen = max(max_count_seen, msg[field])
                    if msg[field] > MAX_PLAYERS:
                        over_limit_msgs.append(f"{t}.{field}={msg[field]}")

            if t == "lobby_joined":
                n = len(msg.get("players", []))
                print(f"  lobby_joined: players={n}, player_count={msg.get('player_count')}")
            elif t == "player_joined":
                player_joined_count += 1
                uname = msg.get("username")
                # kendi user_id ile gelen player_joined olmamalı; lobby mesajı
                # username taşıyor, user_id taşımıyor — ama kendi username'imiz
                # (testoyuncu) ile gelirse şüpheli. Bot isimleri farklıdır.
                if uname == ME:
                    saw_self_player_joined = True
                    print(f"  ⚠️ KENDİ player_joined geldi: username={uname}")
                else:
                    if player_joined_count <= 3:
                        print(f"  player_joined (bot): {uname} count={msg.get('player_count')}")
            elif t == "countdown":
                # gürültüyü azalt, sadece sınır aşımı önemli
                pass
            elif t == "game_starting":
                game_starting_total = msg.get("total_players")
                print(f"  game_starting: total_players={game_starting_total}, "
                      f"real={msg.get('real_players')}, bots={msg.get('bot_count')}, "
                      f"game_id={str(msg.get('game_id'))[:8]}")
                break

    print(f"\n--- ÖZET ---")
    print(f"  toplam player_joined mesajı: {player_joined_count}")
    print(f"  görülen en yüksek sayı: {max_count_seen}")

    ok = True
    print("\n--- KANIT ---")
    # 1) kendi player_joined gelmedi
    if not saw_self_player_joined:
        print("✓ [1] Katılan oyuncu KENDİ player_joined'ını ALMADI")
    else:
        print("✗ [1] Katılan oyuncu kendi player_joined'ını aldı → BUG")
        ok = False
    # 2) 20 sınırı
    if not over_limit_msgs:
        print(f"✓ [2] Hiçbir sayı 20'yi geçmedi (max görülen={max_count_seen})")
    else:
        print(f"✗ [2] 20 sınırını aşan mesajlar: {over_limit_msgs} → BUG")
        ok = False
    # 3) game_starting total_players == 20
    if game_starting_total == MAX_PLAYERS:
        print(f"✓ [3] game_starting total_players={game_starting_total} (=20)")
    else:
        print(f"✗ [3] game_starting total_players={game_starting_total} (beklenen 20)")
        ok = False

    return ok


if __name__ == "__main__":
    ok = asyncio.run(run())
    print("\n=== LOBİ TESTİ:", "GEÇTİ ✅" if ok else "KALDI ❌", "===")
    sys.exit(0 if ok else 1)
