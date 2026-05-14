"""WebSocket lobby endpoint — real-time matchmaking.

This is the skeleton for the lobby system that will be fully
implemented in Week 3 (WebSocket + lobi sistemi + matchmaking).

Flow:
1. Player connects to /ws/lobby
2. Server assigns player to an available lobby (or creates one)
3. Lobby countdown (20 seconds) begins
4. Players see live updates as others join
5. When countdown ends:
   - 20 players: game starts
   - 5-19 players: bots fill remaining slots, game starts
   - <5 real players: lobby cancelled
6. Game rounds are managed through WebSocket messages
"""

import json
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()


class ConnectionManager:
    """Manages active WebSocket connections for lobbies."""

    def __init__(self):
        # lobby_id -> list of (websocket, user_id)
        self.active_connections: dict[str, list[tuple[WebSocket, str]]] = {}

    async def connect(self, lobby_id: str, websocket: WebSocket, user_id: str):
        """Accept a connection and add to lobby."""
        await websocket.accept()
        if lobby_id not in self.active_connections:
            self.active_connections[lobby_id] = []
        self.active_connections[lobby_id].append((websocket, user_id))

    def disconnect(self, lobby_id: str, websocket: WebSocket):
        """Remove a connection from lobby."""
        if lobby_id in self.active_connections:
            self.active_connections[lobby_id] = [
                (ws, uid) for ws, uid in self.active_connections[lobby_id]
                if ws != websocket
            ]
            if not self.active_connections[lobby_id]:
                del self.active_connections[lobby_id]

    async def broadcast_to_lobby(self, lobby_id: str, message: dict):
        """Send a message to all connections in a lobby."""
        if lobby_id in self.active_connections:
            data = json.dumps(message)
            for websocket, _ in self.active_connections[lobby_id]:
                try:
                    await websocket.send_text(data)
                except Exception:
                    pass

    def get_player_count(self, lobby_id: str) -> int:
        """Get the number of connected players in a lobby."""
        return len(self.active_connections.get(lobby_id, []))


# Global connection manager
manager = ConnectionManager()


@router.websocket("/lobby")
async def lobby_websocket(websocket: WebSocket):
    """WebSocket endpoint for lobby matchmaking.

    TODO (Week 3): Full implementation with:
    - JWT authentication on connect
    - Lobby assignment logic
    - 20-second countdown
    - Bot filling
    - Game state management
    - Round progression
    """
    await websocket.accept()

    try:
        # Send welcome message
        await websocket.send_json({
            "type": "connected",
            "message": "QuizRoyale lobby bağlantısı kuruldu.",
            "timestamp": datetime.now(timezone.utc).isoformat(),
        })

        while True:
            # Receive messages from client
            data = await websocket.receive_text()
            message = json.loads(data)

            # Echo back for now (skeleton)
            await websocket.send_json({
                "type": "echo",
                "data": message,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })

    except WebSocketDisconnect:
        pass
    except Exception:
        await websocket.close()
