"""WebSocket lobby endpoint — real-time matchmaking and game start.

Complete implementation of the lobby system:
1.  Player connects with JWT token (query param)
2.  Server sends "connected" handshake immediately
3.  Player sends {"action": "join", ...} to enter matchmaking
4.  Player is assigned to the best available lobby (or a new one)
5.  A 20-second countdown begins on the first real player join
6.  Countdown ticks every 5 s; finishes early when lobby fills
7.  On countdown end: AAS threshold is evaluated, bots fill slots, game starts
8.  Reconnect window: 10 s Redis key lets a player rejoin their lobby after disconnect

Message protocol
----------------
Client → Server:
    {"action": "join",  "username": "...", "display_name": "...", "avatar_id": "..."}
    {"action": "leave"}
    {"action": "emoji",          "emoji": "🔥"}
    {"action": "ready_message",  "message_index": 0}   # preset messages 0-7

Server → Client:
    {"type": "connected",         "user_id": "...", "timestamp": "..."}
    {"type": "lobby_joined",      "lobby_id": "...", "players": [...], "countdown_seconds": 20}
    {"type": "reconnected",       "lobby_id": "...", "players": [...], "remaining_seconds": N}
    {"type": "player_joined",     "username": "...", "avatar_id": "...", "player_count": N}
    {"type": "player_left",       "user_id": "...", "player_count": N}
    {"type": "countdown",         "remaining": N, "player_count": N, "max_players": 20}
    {"type": "game_starting",     "game_id": "...", "players": [...], "total_players": N, "bot_count": N}
    {"type": "lobby_cancelled",   "reason": "..."}
    {"type": "emoji",             "user_id": "...", "emoji": "🔥"}
    {"type": "preset_message",    "user_id": "...", "message": "İyi şanslar!"}
    {"type": "error",             "message": "..."}
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
import time
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.redis_client import get_redis
from app.services.anti_tilt_service import get_bot_difficulty_override
from app.services.cap_service import add_to_queue, get_min_real_players, remove_from_queue
from app.services.matchmaking_service import FIRST_MATCH_MAX_GAMES, matchmaking
from app.services.game_service import create_game
from app.ws.game import run_game
from app.utils.security import decode_token

logger = logging.getLogger(__name__)

router = APIRouter()

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

PRESET_MESSAGES: list[str] = [
    "İyi şanslar!",
    "Tebrikler!",
    "Yakındı!",
    "Harika!",
    "Kolay gelsin!",
    "Vay be!",
    "Haha 😄",
    "GG!",
]

ALLOWED_EMOJIS: frozenset[str] = frozenset({"👏", "😂", "😱", "🔥", "💀", "❤️", "👍", "😎"})

_RECONNECT_KEY_PREFIX = "reconnect:"
_RECONNECT_TTL = settings.RECONNECT_WINDOW_SECONDS  # default 10 s


# ---------------------------------------------------------------------------
# Connection Manager
# ---------------------------------------------------------------------------

class ConnectionManager:
    """Central registry for all live WebSocket connections in lobbies.

    Thread safety: This runs inside a single asyncio event loop (FastAPI /
    uvicorn), so plain dict access is safe — no locks needed.
    """

    def __init__(self) -> None:
        # user_id → (websocket, lobby_id)
        self.connections: dict[str, tuple[WebSocket, str]] = {}
        # lobby_id → set of user_ids currently connected
        self.lobby_members: dict[str, set[str]] = {}
        # lobby_id → running countdown asyncio.Task
        self.countdown_tasks: dict[str, asyncio.Task[None]] = {}
        # lobby_id → list of bot-reveal tasks (unused in simplified flow but kept for extension)
        self.bot_join_tasks: dict[str, list[asyncio.Task[None]]] = {}

    # ------------------------------------------------------------------
    # Connection lifecycle
    # ------------------------------------------------------------------

    async def connect(
        self,
        user_id: str,
        websocket: WebSocket,
        lobby_id: str,
    ) -> None:
        """Register a WebSocket connection for *user_id* inside *lobby_id*."""
        # If reconnecting, clean up stale slot first
        if user_id in self.connections:
            old_lobby = self.connections[user_id][1]
            self._remove_from_members(user_id, old_lobby)

        self.connections[user_id] = (websocket, lobby_id)
        self.lobby_members.setdefault(lobby_id, set()).add(user_id)

    def disconnect(self, user_id: str) -> str | None:
        """Unregister *user_id*.

        Returns:
            The lobby_id the player was in, or ``None`` if not found.
        """
        if user_id not in self.connections:
            return None
        _, lobby_id = self.connections.pop(user_id)
        self._remove_from_members(user_id, lobby_id)
        return lobby_id

    def _remove_from_members(self, user_id: str, lobby_id: str) -> None:
        if lobby_id in self.lobby_members:
            self.lobby_members[lobby_id].discard(user_id)
            if not self.lobby_members[lobby_id]:
                del self.lobby_members[lobby_id]

    # ------------------------------------------------------------------
    # Messaging
    # ------------------------------------------------------------------

    async def send_to_user(self, user_id: str, message: dict[str, Any]) -> None:
        """Send a JSON message to a single connected user.

        Silently swallows send errors (stale connection).
        """
        entry = self.connections.get(user_id)
        if entry is None:
            return
        ws, _ = entry
        try:
            await ws.send_text(json.dumps(message, default=str))
        except Exception:
            logger.debug("send_to_user(%s): send failed, connection may be gone", user_id)

    async def broadcast_to_lobby(
        self,
        lobby_id: str,
        message: dict[str, Any],
        exclude_user_id: str | None = None,
    ) -> None:
        """Broadcast a JSON message to every connected member of *lobby_id*.

        ``exclude_user_id`` verilirse o kullanıcıya gönderilmez. Bu, katılan
        oyuncunun kendi ``player_joined`` yayınını almasını (ve kendini iki
        kez saymasını) engellemek için kullanılır.
        """
        members = self.lobby_members.get(lobby_id)
        if not members:
            return
        payload = json.dumps(message, default=str)
        for uid in list(members):
            if exclude_user_id is not None and uid == exclude_user_id:
                continue
            entry = self.connections.get(uid)
            if entry is None:
                continue
            ws, _ = entry
            try:
                await ws.send_text(payload)
            except Exception:
                logger.debug("broadcast_to_lobby(%s): send to %s failed", lobby_id, uid)

    # ------------------------------------------------------------------
    # Lobby helpers
    # ------------------------------------------------------------------

    def get_lobby_user_ids(self, lobby_id: str) -> set[str]:
        """Return the set of user_ids connected to *lobby_id*."""
        return set(self.lobby_members.get(lobby_id, set()))

    # ------------------------------------------------------------------
    # Countdown management
    # ------------------------------------------------------------------

    async def start_countdown(self, lobby_id: str) -> None:
        """Start the 20-second lobby countdown if not already running."""
        if lobby_id in self.countdown_tasks:
            return  # Already ticking
        task = asyncio.create_task(
            self._countdown_loop(lobby_id),
            name=f"countdown-{lobby_id}",
        )
        self.countdown_tasks[lobby_id] = task
        # Botları countdown boyunca GÖRÜNÜR şekilde ekle (lobi 20'ye dolsun).
        fill_task = asyncio.create_task(
            self._bot_fill_loop(lobby_id),
            name=f"botfill-{lobby_id}",
        )
        self.bot_join_tasks.setdefault(lobby_id, []).append(fill_task)

    def cancel_countdown(self, lobby_id: str) -> None:
        """Cancel the countdown task for *lobby_id* if running."""
        task = self.countdown_tasks.pop(lobby_id, None)
        if task and not task.done():
            task.cancel()
        for t in self.bot_join_tasks.pop(lobby_id, []):
            if not t.done():
                t.cancel()

    async def _bot_fill_loop(self, lobby_id: str) -> None:
        """Countdown boyunca botları kademeli ekleyip ``player_joined`` yayınlar.

        Böylece lobi 20 kişiye dolarken oyuncular (3D avatar + isim) görünür.
        Gerçek oyuncular her zaman önceliklidir; lobi dolunca durur. Kalan
        boş slotlar oyun başında ``fill_with_bots`` ile tamamlanır.
        """
        await asyncio.sleep(random.uniform(1.0, 2.2))
        start = time.monotonic()
        while True:
            lobby = matchmaking.get_lobby(lobby_id)
            if lobby is None or lobby.status in ("cancelled", "starting", "in_game"):
                return
            # Son ~3 sn temiz kalsın (15 sn sayaca göre); lobi dolduysa dur.
            if lobby.is_full or (time.monotonic() - start) > 11.0:
                return
            bot = lobby.add_one_bot()
            if bot is not None:
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "player_joined",
                    "username": bot["bot_name"],
                    "avatar_id": bot["avatar_id"],
                    "frame": bot.get("frame"),
                    "name_color": bot.get("name_color"),
                    "effect": bot.get("effect"),
                    "player_count": lobby.total_count,
                })
            await asyncio.sleep(random.uniform(0.5, 1.1))

    async def _countdown_loop(self, lobby_id: str) -> None:
        """Run the 20-second countdown for a lobby.

        Broadcasts a ``countdown`` tick every 5 s and every second during the
        final 5 s.  Breaks early when the lobby fills (20 real players).

        On expiry: calls AAS to get the min-real-player threshold, resolves
        the lobby (bot fill + status transition), then broadcasts either
        ``game_starting`` or ``lobby_cancelled``.
        """
        lobby = matchmaking.get_lobby(lobby_id)
        if lobby:
            lobby.status = "countdown"

        remaining = settings.LOBBY_TIMEOUT_SECONDS
        lobby_start_ts = time.monotonic()

        try:
            while remaining > 0:
                lobby = matchmaking.get_lobby(lobby_id)
                if lobby is None or lobby.status == "cancelled":
                    return

                # Lobi 20'ye dolduysa (gerçek + bot) süreyi yarıda kes, hemen başlat.
                if lobby.total_count >= settings.MAX_PLAYERS:
                    await self.broadcast_to_lobby(lobby_id, {
                        "type": "countdown",
                        "remaining": 0,
                        "player_count": lobby.real_player_count,
                        "max_players": settings.MAX_PLAYERS,
                    })
                    break

                # Her saniye yayınla → 20, 19, 18, ... tek tek geri sayım.
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "countdown",
                    "remaining": remaining,
                    "player_count": lobby.real_player_count,
                    "max_players": settings.MAX_PLAYERS,
                })

                await asyncio.sleep(1)
                remaining -= 1

            # ----------------------------------------------------------
            # Countdown finished — resolve lobby
            # ----------------------------------------------------------
            elapsed = time.monotonic() - lobby_start_ts
            threshold = await get_min_real_players(
                user_games_played=999,
                user_wait_seconds=elapsed,
            )

            result = matchmaking.resolve_lobby(lobby_id, min_real_players=threshold)
            lobby = matchmaking.get_lobby(lobby_id)

            if result == "start" and lobby:
                lobby.game_id = str(uuid_mod.uuid4())
                lobby.status = "in_game"

                # Register game and start the game loop.
                # KRİTİK: is_tournament BURADA geçilmeli — yoksa engine
                # is_tournament=False ile active_games'e girer, run_game o
                # hazır (yanlış bayraklı) engine'i yeniden kullanır ve maç
                # sonu ranked sezon puanı 3x ASLA uygulanmaz.
                engine = create_game(
                    game_id=lobby.game_id,
                    players=lobby.players,
                    bots=lobby.bots,
                    is_tournament=lobby.is_tournament,
                )
                # İlk-maç senaryosu: botların final (slider) tahmin sapması
                # genişletilir → yeni oyuncunun finali kazanma şansı artar.
                engine.generous_bot_guesses = (lobby.bot_mix == "first_match")
                asyncio.create_task(
                    run_game(
                        lobby.game_id,
                        lobby.players,
                        lobby.bots,
                        is_tournament=lobby.is_tournament,
                    ),
                    name=f"game-{lobby.game_id}",
                )

                # Turnuva maçı GERÇEKTEN başladı → giriş biletlerini tüket
                # (artık iade edilmez). run_game ayrıca hiç gerçek oyuncu
                # bağlanmazsa iptal edip iade eder; bu yüzden burada tüketmeyi
                # run_game'e bırakıyoruz — sadece turnuva değilse no-op. Aşağıda
                # consume, oyun gerçekten oyuncularla başladığında game.py'de
                # yapılır. (Çift güvenlik için burada bir şey yapmıyoruz.)

                await self.broadcast_to_lobby(lobby_id, {
                    "type": "game_starting",
                    "game_id": lobby.game_id,
                    "players": lobby.player_list_for_client(),
                    "total_players": lobby.total_count,
                    "real_players": lobby.real_player_count,
                    "bot_count": len(lobby.bots),
                })
                logger.info(
                    "Lobby %s started: game_id=%s real=%d bots=%d",
                    lobby_id,
                    lobby.game_id,
                    lobby.real_player_count,
                    len(lobby.bots),
                )
            else:
                # result == "cancel" (no real players at all)
                real_count = lobby.real_player_count if lobby else 0
                # Money-safe: maç HİÇ başlamadı → turnuva giriş ücretlerini iade et.
                if lobby and lobby.is_tournament:
                    await _refund_tournament_lobby(lobby)
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "lobby_cancelled",
                    "reason": "Yeterli oyuncu bulunamadı.",
                    "player_count": real_count,
                    "min_required": settings.MIN_PLAYERS,
                })
                matchmaking.remove_lobby(lobby_id)
                logger.info("Lobby %s cancelled (no real players)", lobby_id)

        except asyncio.CancelledError:
            logger.debug("Countdown for lobby %s cancelled", lobby_id)
            raise
        except Exception:
            logger.exception("Unexpected error in countdown loop for lobby %s", lobby_id)
        finally:
            self.countdown_tasks.pop(lobby_id, None)

    # ------------------------------------------------------------------
    # Bot-reveal scheduling (stub — bots added silently on resolve)
    # ------------------------------------------------------------------

    async def schedule_bot_reveals(
        self,
        lobby_id: str,
        bot_names_and_avatars: list[tuple[str, str]],
        schedule_offsets: list[float],
    ) -> None:
        """Schedule per-bot ``player_joined`` broadcasts at the given offsets.

        This is intentionally a no-op in the current simplified flow —
        bots are added silently at game-start so real players cannot
        distinguish them.  The method is retained for future UI experiments
        (e.g. showing a blurred "player joining…" placeholder).

        Args:
            lobby_id: Target lobby.
            bot_names_and_avatars: List of (bot_name, avatar_id) pairs.
            schedule_offsets: Seconds-from-now at which each bot should appear.
        """
        # Bots are revealed only in `game_starting` payload; no preview reveals.
        pass


# ---------------------------------------------------------------------------
# Module-level singleton
# ---------------------------------------------------------------------------

manager = ConnectionManager()


# ---------------------------------------------------------------------------
# Redis reconnect helpers
# ---------------------------------------------------------------------------

async def _store_reconnect_key(user_id: str, lobby_id: str) -> None:
    """Write ``reconnect:{user_id}`` → lobby_id into Redis with a 10-second TTL."""
    try:
        client = await get_redis()
        await client.set(
            f"{_RECONNECT_KEY_PREFIX}{user_id}",
            lobby_id,
            ex=_RECONNECT_TTL,
        )
    except Exception:
        logger.warning("Could not store reconnect key for user %s", user_id)


async def _pop_reconnect_key(user_id: str) -> str | None:
    """Return and delete the stored lobby_id for *user_id*, or None if not set."""
    try:
        client = await get_redis()
        key = f"{_RECONNECT_KEY_PREFIX}{user_id}"
        lobby_id: str | None = await client.get(key)
        if lobby_id:
            await client.delete(key)
        return lobby_id
    except Exception:
        logger.warning("Could not retrieve reconnect key for user %s", user_id)
        return None


# ---------------------------------------------------------------------------
# Turnuva bileti iadesi (money-safe)
# ---------------------------------------------------------------------------

async def _refund_tournament_lobby(lobby: Any) -> None:
    """Bir turnuva lobisindeki gerçek oyuncuların pending biletlerini iade et.

    Lobi maç başlamadan iptal olduğunda (yeterli oyuncu yok) çağrılır. Sadece
    gerçek oyuncular (bot değil) iade edilir; idempotent (pending olmayan bilet
    atlanır). Hata lobi temizliğini engellemesin diye sessizce yutulur.
    """
    try:
        from app.services.tournament_service import TournamentService

        user_ids = [p["user_id"] for p in lobby.players if p.get("user_id")]
        if not user_ids:
            return
        refunded = await TournamentService.refund_pending_for_users(user_ids)
        if refunded:
            logger.info(
                "Lobby %s turnuva iadesi: %d oyuncu iade aldı",
                lobby.lobby_id, refunded,
            )
    except Exception:
        logger.exception("Turnuva lobi iadesi başarısız (lobby %s)", lobby.lobby_id)


# ---------------------------------------------------------------------------
# Savunmacı köprü: lobi WS'ine yanlışlıkla gelen oyun mesajını oyun motoruna ilet
# ---------------------------------------------------------------------------

def _route_game_message_from_lobby(user_id: str, message: dict[str, Any]) -> bool:
    """İstemci oyun mesajını (submit_answer vb.) yanlışlıkla LOBİ WS'ine
    gönderdiğinde, kullanıcının aktif oyun motoruna yönlendir.

    Submit'in sessizce düşmesini önleyen savunmacı köprü. Kullanıcının dahil
    olduğu aktif oyunu ``active_games`` içinde user_id ile bulur ve mevcut
    ``_handle_submit_answer`` mantığını yeniden kullanır. İade değeri yalnızca
    teşhis amaçlıdır (True = bir motora iletildi).
    """
    msg_type = message.get("type", "")
    if msg_type != "submit_answer":
        # Şimdilik yalnızca submit kritik; emoji/ready oyun akışını etkilemez.
        return False
    try:
        from app.services.game_service import active_games
        from app.ws.game import _handle_submit_answer
    except Exception:
        return False

    for engine in active_games.values():
        if any(
            p.user_id == user_id and not p.is_bot
            for p in engine.players.values()
        ):
            try:
                _handle_submit_answer(engine, user_id, message)
            except Exception:
                logger.exception(
                    "Lobi->oyun submit köprüsü hata (user %s, game %s)",
                    user_id, getattr(engine, "game_id", "?"),
                )
                return False
            return True
    return False


# ---------------------------------------------------------------------------
# JWT authentication helper
# ---------------------------------------------------------------------------

async def _fetch_user_cosmetics(user_id: str) -> dict[str, Any] | None:
    """Bir oyuncunun kuşanılmış kozmetiklerini DB'den çek (lobi vitrini için).

    {"frame", "name_color", "effect"} döner; hata olursa None (kozmetiksiz
    devam). Tek kullanıcı için tek hafif sorgu — lobiye katılımı bloklamaz.
    """
    try:
        from app.database import async_session_factory
        from app.services.cosmetics_service import CosmeticsService

        async with async_session_factory() as db:
            equipped = await CosmeticsService.equipped_for_users(db, [user_id])
        return equipped.get(user_id)
    except Exception:
        logger.debug("Kozmetik çekilemedi (user %s)", user_id)
        return None


async def _fetch_games_played(user_id: str) -> int | None:
    """Oyuncunun toplam oynanmış maç sayısını DB'den çek (ilk-maç senaryosu).

    User.games_played alanını okur (AAS/cap_service'in kullandığı bilgiyle
    aynı kaynak). Hata olursa None döner → senaryo tetiklenmez, lobi normal
    karışımla devam eder (katılımı asla bloklamaz).
    """
    try:
        from app.database import async_session_factory
        from app.services.user_service import UserService

        async with async_session_factory() as db:
            user = await UserService.get_user_by_id(db, user_id)
        if user is None:
            return None
        return int(user.games_played or 0)
    except Exception:
        logger.debug("games_played çekilemedi (user %s)", user_id)
        return None


async def _apply_bot_mix_overrides(lobby: Any, user_id: str) -> None:
    """Katılan oyuncuya göre lobinin bot karışım override'ını belirle.

    Öncelik sırası (set_bot_mix içinde de korunur):
      1. İlk-maç senaryosu: oyuncunun toplam maçı < FIRST_MATCH_MAX_GAMES ise
         karışım "first_match" (≈9 easy + 2 medium + 0 hard) olur.
      2. Anti-tilt: 3 üst üste kayıpta karışım "easy_heavy" (%80 easy) olur.
      3. Varsayılan karışım.

    Sadece NORMAL eşleşme lobileri için; turnuva lobisinde set_bot_mix no-op.
    Hatalar katılımı asla engellemez (best-effort).
    """
    try:
        games_played = await _fetch_games_played(user_id)
        if games_played is not None and games_played < FIRST_MATCH_MAX_GAMES:
            lobby.set_bot_mix("first_match")
            return
        # Anti-tilt override'ı (yalnızca ilk-maç tetiklenmediyse anlamlı;
        # set_bot_mix zaten önceliği korur).
        tilt_override = await get_bot_difficulty_override(user_id)
        if tilt_override == "easy_heavy":
            lobby.set_bot_mix("easy_heavy")
    except Exception:
        logger.debug("Bot karışım override'ı uygulanamadı (user %s)", user_id)


def _authenticate_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT access token.

    Returns the payload dict on success, or ``None`` on any failure.
    """
    try:
        return decode_token(token, expected_type="access")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/lobby")
async def lobby_websocket(websocket: WebSocket) -> None:
    """WebSocket endpoint for lobby matchmaking.

    Connection URL: ``ws://host/ws/lobby?token=<JWT_ACCESS_TOKEN>``
    """
    # ------------------------------------------------------------------
    # 1. Authenticate before accepting the connection
    # ------------------------------------------------------------------
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token gerekli.")
        return

    payload = _authenticate_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Geçersiz veya süresi dolmuş token.")
        return

    user_id: str = payload.get("sub", "")
    if not user_id:
        await websocket.close(code=4001, reason="Token içinde kullanıcı bilgisi yok.")
        return

    await websocket.accept()

    # ------------------------------------------------------------------
    # 2. Send connection handshake
    # ------------------------------------------------------------------
    await websocket.send_text(json.dumps({
        "type": "connected",
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    current_lobby_id: str | None = None

    try:
        while True:
            raw = await websocket.receive_text()

            # Parse JSON
            try:
                message: dict[str, Any] = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Geçersiz JSON formatı.",
                }))
                continue

            action: str = message.get("action", "")

            # --------------------------------------------------------------
            # SAVUNMACI KÖPRÜ: Oyun başladıktan sonra istemcinin lobi
            # provider'ı hemen dispose olmayabilir; bu durumda istemci
            # submit'i (veya emoji/diğer oyun mesajlarını) yanlışlıkla LOBİ
            # WS'ine gönderebilir. Lobi handler bunu eskiden "Bilinmeyen
            # action" diye sessizce düşürüyordu → cevap sunucuya hiç ulaşmıyor,
            # oyuncu answer=None ile eleniyordu. İstemci mesajları `type`
            # anahtarıyla gelir ({"type":"submit_answer",...}); lobi ise
            # `action` bekler. `action` yoksa ama `type` bir oyun mesajıysa,
            # mesajı kullanıcının AKTİF oyun motoruna yönlendir.
            msg_type: str = message.get("type", "")
            if not action and msg_type in ("submit_answer", "emoji", "lock_answer", "ready"):
                _route_game_message_from_lobby(user_id, message)
                continue

            # --------------------------------------------------------------
            # action: join
            # --------------------------------------------------------------
            if action == "join":
                username: str = message.get("username") or f"player_{user_id[:6]}"
                display_name: str = message.get("display_name") or username
                avatar_id: str = message.get("avatar_id") or "default_01"
                # Turnuva modu bayrağı: client /api/tournament/enter ile giriş
                # ücretini ödedikten sonra mode="tournament" ile katılır. Normal
                # maç davranışı DEĞİŞMEZ (varsayılan False).
                is_tournament: bool = (
                    message.get("mode") == "tournament"
                    or bool(message.get("is_tournament"))
                )

                # -- Check for reconnect window --
                prior_lobby_id = await _pop_reconnect_key(user_id)
                if prior_lobby_id:
                    prior_lobby = matchmaking.get_lobby(prior_lobby_id)
                    # Lobby still alive and player still listed as member
                    if prior_lobby and any(
                        p["user_id"] == user_id for p in prior_lobby.players
                    ):
                        current_lobby_id = prior_lobby_id
                        await manager.connect(user_id, websocket, prior_lobby_id)
                        await add_to_queue(user_id)

                        # Compute remaining countdown seconds
                        elapsed_secs = int(
                            (datetime.now(timezone.utc) - prior_lobby.created_at).total_seconds()
                        )
                        remaining_secs = max(
                            0, settings.LOBBY_TIMEOUT_SECONDS - elapsed_secs
                        )

                        await websocket.send_text(json.dumps({
                            "type": "reconnected",
                            "lobby_id": prior_lobby_id,
                            "players": prior_lobby.player_list_for_client(),
                            "remaining_seconds": remaining_secs,
                        }, default=str))

                        logger.info("User %s reconnected to lobby %s", user_id, prior_lobby_id)
                        continue  # Done — back to receive loop

                # -- Normal join path --
                # Oyuncunun kuşanılmış kozmetiklerini DB'den çek (vitrin için).
                # Tek kullanıcı, tek kısa sorgu; hata lobiye katılımı engellemez.
                player_cosmetics = await _fetch_user_cosmetics(user_id)
                lobby = matchmaking.join_or_create(
                    user_id=user_id,
                    username=username,
                    display_name=display_name,
                    avatar_id=avatar_id,
                    cosmetics=player_cosmetics,
                    is_tournament=is_tournament,
                )
                current_lobby_id = lobby.lobby_id

                # İlk-maç senaryosu + anti-tilt bot karışımı (turnuva HARİÇ).
                if not is_tournament:
                    await _apply_bot_mix_overrides(lobby, user_id)

                await manager.connect(user_id, websocket, lobby.lobby_id)
                await add_to_queue(user_id)

                # Notify the joining player
                await websocket.send_text(json.dumps({
                    "type": "lobby_joined",
                    "lobby_id": lobby.lobby_id,
                    "players": lobby.player_list_for_client(),
                    "player_count": lobby.real_player_count,
                    "max_players": settings.MAX_PLAYERS,
                    "countdown_seconds": settings.LOBBY_TIMEOUT_SECONDS,
                }, default=str))

                # Notify existing lobby members that a new player arrived.
                # Katılan oyuncunun KENDİSİNE gönderme — yoksa kendini iki kez
                # sayar (lobby_joined zaten kendisini listede gönderdi).
                await manager.broadcast_to_lobby(
                    lobby.lobby_id,
                    {
                        "type": "player_joined",
                        "username": username,
                        "display_name": display_name,
                        "avatar_id": avatar_id,
                        "frame": (player_cosmetics or {}).get("frame"),
                        "name_color": (player_cosmetics or {}).get("name_color"),
                        "effect": (player_cosmetics or {}).get("effect"),
                        "player_count": lobby.real_player_count,
                        "max_players": settings.MAX_PLAYERS,
                    },
                    exclude_user_id=user_id,
                )

                # Start countdown on first player join
                await manager.start_countdown(lobby.lobby_id)

                logger.info(
                    "User %s joined lobby %s (%d/%d)",
                    user_id,
                    lobby.lobby_id,
                    lobby.real_player_count,
                    settings.MAX_PLAYERS,
                )

            # --------------------------------------------------------------
            # action: leave
            # --------------------------------------------------------------
            elif action == "leave":
                if current_lobby_id:
                    left_lobby = matchmaking.leave_lobby(user_id)
                    manager.disconnect(user_id)
                    await remove_from_queue(user_id)

                    if left_lobby:
                        await manager.broadcast_to_lobby(left_lobby.lobby_id, {
                            "type": "player_left",
                            "user_id": user_id,
                            "player_count": left_lobby.real_player_count,
                        })
                        # Cancel countdown if lobby is now empty
                        if left_lobby.real_player_count == 0:
                            manager.cancel_countdown(left_lobby.lobby_id)

                    current_lobby_id = None

                    await websocket.send_text(json.dumps({
                        "type": "lobby_left",
                        "message": "Lobiden ayrıldınız.",
                    }))

                    logger.info("User %s left lobby voluntarily", user_id)

            # --------------------------------------------------------------
            # action: emoji
            # --------------------------------------------------------------
            elif action == "emoji":
                emoji: str = message.get("emoji", "")
                if emoji not in ALLOWED_EMOJIS:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Geçersiz emoji.",
                    }))
                    continue
                if not current_lobby_id:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Bir lobiye katılmadan emoji gönderemezsiniz.",
                    }))
                    continue
                await manager.broadcast_to_lobby(current_lobby_id, {
                    "type": "emoji",
                    "user_id": user_id,
                    "emoji": emoji,
                })

            # --------------------------------------------------------------
            # action: ready_message
            # --------------------------------------------------------------
            elif action == "ready_message":
                if not current_lobby_id:
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": "Bir lobiye katılmadan mesaj gönderemezsiniz.",
                    }))
                    continue
                try:
                    idx = int(message.get("message_index", -1))
                except (TypeError, ValueError):
                    idx = -1

                if idx < 0 or idx >= len(PRESET_MESSAGES):
                    await websocket.send_text(json.dumps({
                        "type": "error",
                        "message": f"Geçersiz mesaj indeksi. 0-{len(PRESET_MESSAGES) - 1} arasında olmalı.",
                    }))
                    continue

                await manager.broadcast_to_lobby(current_lobby_id, {
                    "type": "preset_message",
                    "user_id": user_id,
                    "message": PRESET_MESSAGES[idx],
                })

            # --------------------------------------------------------------
            # Unknown action
            # --------------------------------------------------------------
            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Bilinmeyen action: '{action}'",
                }))

    except WebSocketDisconnect:
        logger.info("User %s WebSocket disconnected", user_id)
    except Exception:
        logger.exception("Unhandled error in lobby_websocket for user %s", user_id)
    finally:
        # ------------------------------------------------------------------
        # Cleanup on any exit path
        # ------------------------------------------------------------------
        if current_lobby_id:
            # Store reconnect key so player can resume within 10 s
            await _store_reconnect_key(user_id, current_lobby_id)

            # Notify remaining lobby members
            left_lobby = matchmaking.leave_lobby(user_id)
            if left_lobby:
                await manager.broadcast_to_lobby(left_lobby.lobby_id, {
                    "type": "player_left",
                    "user_id": user_id,
                    "player_count": left_lobby.real_player_count,
                })
                # If lobby is now empty and not yet started, cancel countdown
                if (
                    left_lobby.real_player_count == 0
                    and left_lobby.status not in ("in_game", "starting")
                ):
                    manager.cancel_countdown(left_lobby.lobby_id)

        manager.disconnect(user_id)
        await remove_from_queue(user_id)
        logger.debug("Cleanup complete for user %s", user_id)
