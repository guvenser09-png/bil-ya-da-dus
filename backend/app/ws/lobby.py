"""WebSocket lobby endpoint — real-time matchmaking and game play.

Complete implementation of the lobby system:
1. Player connects with JWT token
2. Server assigns player to the best available lobby
3. 20-second countdown begins when first player joins
4. Real-time updates as players join/leave
5. When countdown ends: start game or cancel
6. Game rounds are managed through WebSocket messages
"""

import asyncio
import json
import uuid as uuid_mod
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from jose import JWTError

from app.config import settings
from app.services.matchmaking_service import matchmaking
from app.utils.security import decode_token

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections for lobbies."""

    def __init__(self):
        # user_id -> (websocket, lobby_id)
        self.connections: dict[str, tuple[WebSocket, str]] = {}
        # lobby_id -> set of user_ids
        self.lobby_members: dict[str, set[str]] = {}
        # lobby_id -> countdown task
        self.countdown_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, user_id: str, websocket: WebSocket, lobby_id: str):
        """Register a WebSocket connection."""
        self.connections[user_id] = (websocket, lobby_id)
        if lobby_id not in self.lobby_members:
            self.lobby_members[lobby_id] = set()
        self.lobby_members[lobby_id].add(user_id)

    def disconnect(self, user_id: str):
        """Unregister a WebSocket connection."""
        if user_id in self.connections:
            _, lobby_id = self.connections.pop(user_id)
            if lobby_id in self.lobby_members:
                self.lobby_members[lobby_id].discard(user_id)
                if not self.lobby_members[lobby_id]:
                    del self.lobby_members[lobby_id]

    async def send_to_user(self, user_id: str, message: dict):
        """Send a message to a specific user."""
        if user_id in self.connections:
            ws, _ = self.connections[user_id]
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                pass

    async def broadcast_to_lobby(self, lobby_id: str, message: dict):
        """Send a message to all users in a lobby."""
        if lobby_id in self.lobby_members:
            data = json.dumps(message, default=str)
            for user_id in list(self.lobby_members[lobby_id]):
                if user_id in self.connections:
                    ws, _ = self.connections[user_id]
                    try:
                        await ws.send_text(data)
                    except Exception:
                        pass

    def get_lobby_user_ids(self, lobby_id: str) -> set[str]:
        return self.lobby_members.get(lobby_id, set())

    async def start_countdown(self, lobby_id: str):
        """Start the 20-second lobby countdown."""
        if lobby_id in self.countdown_tasks:
            return  # Already running

        task = asyncio.create_task(self._countdown_loop(lobby_id))
        self.countdown_tasks[lobby_id] = task

    async def _countdown_loop(self, lobby_id: str):
        """Run the countdown timer for a lobby."""
        remaining = settings.LOBBY_TIMEOUT_SECONDS

        lobby = matchmaking.get_lobby(lobby_id)
        if lobby:
            lobby.status = "countdown"

        while remaining > 0:
            lobby = matchmaking.get_lobby(lobby_id)
            if not lobby or lobby.status == "cancelled":
                break

            # Check if lobby is full — start immediately
            if lobby.is_full:
                break

            # Broadcast countdown update every 5 seconds (and last 5)
            if remaining <= 5 or remaining % 5 == 0:
                await self.broadcast_to_lobby(lobby_id, {
                    "type": "countdown",
                    "remaining": remaining,
                    "player_count": lobby.real_player_count,
                    "max_players": settings.MAX_PLAYERS,
                })

            await asyncio.sleep(1)
            remaining -= 1

        # Countdown finished — resolve lobby
        result = matchmaking.resolve_lobby(lobby_id)
        lobby = matchmaking.get_lobby(lobby_id)

        if result == "start" and lobby:
            # Generate game_id
            lobby.game_id = str(uuid_mod.uuid4())
            lobby.status = "in_game"

            await self.broadcast_to_lobby(lobby_id, {
                "type": "game_starting",
                "game_id": lobby.game_id,
                "players": lobby.player_list_for_client(),
                "total_players": lobby.total_count,
                "real_players": lobby.real_player_count,
                "bot_count": len(lobby.bots),
            })
        elif result == "cancel":
            await self.broadcast_to_lobby(lobby_id, {
                "type": "lobby_cancelled",
                "reason": "Yeterli oyuncu bulunamadı.",
                "player_count": lobby.real_player_count if lobby else 0,
                "min_required": settings.MIN_PLAYERS,
            })
            # Clean up
            matchmaking.remove_lobby(lobby_id)

        # Clean up countdown task
        self.countdown_tasks.pop(lobby_id, None)


# Global connection manager
manager = ConnectionManager()


def _authenticate_token(token: str) -> dict | None:
    """Validate JWT token from WebSocket query params."""
    try:
        payload = decode_token(token, expected_type="access")
        return payload
    except Exception:
        return None


@router.websocket("/lobby")
async def lobby_websocket(websocket: WebSocket):
    """WebSocket endpoint for lobby matchmaking.

    Connection: ws://host/ws/lobby?token=<JWT_ACCESS_TOKEN>

    Client -> Server messages:
        {"action": "join"}              — Join the matchmaking queue
        {"action": "leave"}             — Leave the current lobby
        {"action": "emoji", "emoji": "🔥"} — Send emoji reaction

    Server -> Client messages:
        {"type": "connected"}           — Connection established
        {"type": "lobby_joined"}        — Assigned to a lobby
        {"type": "player_joined"}       — Another player joined
        {"type": "player_left"}         — A player left
        {"type": "countdown"}           — Countdown tick
        {"type": "game_starting"}       — Game is starting
        {"type": "lobby_cancelled"}     — Not enough players
        {"type": "emoji"}               — Emoji from another player
        {"type": "error"}               — Error message
    """
    # Authenticate via query parameter
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token gerekli.")
        return

    payload = _authenticate_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Geçersiz token.")
        return

    user_id = payload.get("sub")
    if not user_id:
        await websocket.close(code=4001, reason="Geçersiz token.")
        return

    await websocket.accept()

    # Send welcome
    await websocket.send_text(json.dumps({
        "type": "connected",
        "message": "QuizRoyale lobby bağlantısı kuruldu.",
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }))

    current_lobby_id = None

    try:
        while True:
            data = await websocket.receive_text()
            try:
                message = json.loads(data)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error", "message": "Geçersiz JSON."
                }))
                continue

            action = message.get("action")

            if action == "join":
                # Join matchmaking
                # We need user info — for now use user_id as username
                username = message.get("username", f"player_{user_id[:6]}")
                display_name = message.get("display_name", username)
                avatar_id = message.get("avatar_id", "default_01")

                lobby = matchmaking.join_or_create(
                    user_id=user_id,
                    username=username,
                    display_name=display_name,
                    avatar_id=avatar_id,
                )
                current_lobby_id = lobby.lobby_id
                await manager.connect(user_id, websocket, lobby.lobby_id)

                # Notify the joining player
                await websocket.send_text(json.dumps({
                    "type": "lobby_joined",
                    "lobby_id": lobby.lobby_id,
                    "players": lobby.player_list_for_client(),
                    "player_count": lobby.real_player_count,
                    "max_players": settings.MAX_PLAYERS,
                    "countdown_seconds": settings.LOBBY_TIMEOUT_SECONDS,
                }, default=str))

                # Notify others in lobby
                await manager.broadcast_to_lobby(lobby.lobby_id, {
                    "type": "player_joined",
                    "username": username,
                    "display_name": display_name,
                    "avatar_id": avatar_id,
                    "player_count": lobby.real_player_count,
                    "max_players": settings.MAX_PLAYERS,
                })

                # Start countdown if not already started
                await manager.start_countdown(lobby.lobby_id)

                # If lobby is full, the countdown loop will detect and start immediately

            elif action == "leave":
                if current_lobby_id:
                    lobby = matchmaking.leave_lobby(user_id)
                    manager.disconnect(user_id)

                    if lobby:
                        await manager.broadcast_to_lobby(lobby.lobby_id, {
                            "type": "player_left",
                            "user_id": user_id,
                            "player_count": lobby.real_player_count,
                        })
                    current_lobby_id = None

                    await websocket.send_text(json.dumps({
                        "type": "lobby_left",
                        "message": "Lobiden ayrıldınız.",
                    }))

            elif action == "emoji":
                emoji = message.get("emoji", "")
                allowed_emojis = {"👏", "😂", "😱", "🔥", "💀", "❤️", "👍", "😎"}
                if emoji in allowed_emojis and current_lobby_id:
                    await manager.broadcast_to_lobby(current_lobby_id, {
                        "type": "emoji",
                        "user_id": user_id,
                        "emoji": emoji,
                    })

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Bilinmeyen action: {action}",
                }))

    except WebSocketDisconnect:
        pass
    except Exception:
        pass
    finally:
        # Clean up on disconnect
        if current_lobby_id:
            lobby = matchmaking.leave_lobby(user_id)
            if lobby:
                await manager.broadcast_to_lobby(lobby.lobby_id, {
                    "type": "player_left",
                    "user_id": user_id,
                    "player_count": lobby.real_player_count,
                })
        manager.disconnect(user_id)
