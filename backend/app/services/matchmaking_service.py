"""Matchmaking service — lobby creation, player assignment, countdown.

Lobby lifecycle (from CLAUDE.md Section 2.1):
1. Every 20 seconds a new lobby opens
2. Multiple lobbies can run in parallel
3. Player joins the lobby with the most free slots
4. Live counter: "Oyuncu aranıyor... 7/20"
5. When countdown ends:
   - 20 players → game starts immediately
   - 5-19 real players → fill with bots, game starts
   - <5 real players → lobby cancelled

All lobby state is stored in Redis for real-time access.
"""

import asyncio
import json
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.redis_client import get_redis
from app.services.bot_service import generate_bot_name


# --- Lobby Data Structures ---

class LobbyState:
    """In-memory representation of a lobby's state."""

    def __init__(self, lobby_id: str):
        self.lobby_id = lobby_id
        self.players: list[dict] = []  # [{user_id, username, display_name, avatar_id}]
        self.bots: list[dict] = []     # [{bot_name, difficulty, avatar_id}]
        self.created_at = datetime.now(timezone.utc)
        self.countdown_seconds = settings.LOBBY_TIMEOUT_SECONDS
        self.status = "waiting"  # waiting, countdown, starting, cancelled, in_game
        self.game_id: str | None = None

    @property
    def real_player_count(self) -> int:
        return len(self.players)

    @property
    def total_count(self) -> int:
        return len(self.players) + len(self.bots)

    @property
    def is_full(self) -> bool:
        return self.real_player_count >= settings.MAX_PLAYERS

    def add_player(self, user_id: str, username: str, display_name: str, avatar_id: str) -> bool:
        """Add a real player to the lobby. Returns False if full."""
        if self.is_full:
            return False
        if any(p["user_id"] == user_id for p in self.players):
            return False  # Already in lobby
        self.players.append({
            "user_id": user_id,
            "username": username,
            "display_name": display_name,
            "avatar_id": avatar_id,
        })
        return True

    def remove_player(self, user_id: str) -> bool:
        """Remove a player from the lobby."""
        before = len(self.players)
        self.players = [p for p in self.players if p["user_id"] != user_id]
        return len(self.players) < before

    def fill_with_bots(self) -> int:
        """Fill remaining slots with bots. Returns number of bots added."""
        used_names = {p.get("username", "") for p in self.players}
        used_names.update(b["bot_name"] for b in self.bots)

        bots_needed = settings.MAX_PLAYERS - self.total_count
        bots_added = 0

        # Distribute difficulty: early bots are easy, later harder
        difficulties = ["easy"] * 5 + ["medium"] * 7 + ["hard"] * 8
        bot_avatars = [f"default_{str(i).zfill(2)}" for i in range(1, 11)]

        import random
        for i in range(bots_needed):
            name = generate_bot_name()
            # Ensure unique name
            attempts = 0
            while name in used_names and attempts < 50:
                name = generate_bot_name()
                attempts += 1

            difficulty = difficulties[min(i, len(difficulties) - 1)]
            self.bots.append({
                "bot_name": name,
                "difficulty": difficulty,
                "avatar_id": random.choice(bot_avatars),
            })
            used_names.add(name)
            bots_added += 1

        return bots_added

    def to_dict(self) -> dict:
        """Serialize lobby state for Redis/WebSocket."""
        return {
            "lobby_id": self.lobby_id,
            "players": self.players,
            "bots": [{"bot_name": b["bot_name"], "avatar_id": b["avatar_id"]} for b in self.bots],
            "real_player_count": self.real_player_count,
            "total_count": self.total_count,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "game_id": self.game_id,
        }

    def player_list_for_client(self) -> list[dict]:
        """Get combined player list for client (bots look like real players)."""
        result = []
        for p in self.players:
            result.append({
                "username": p["username"],
                "display_name": p["display_name"],
                "avatar_id": p["avatar_id"],
                "is_ready": True,
            })
        for b in self.bots:
            result.append({
                "username": b["bot_name"],
                "display_name": b["bot_name"],
                "avatar_id": b["avatar_id"],
                "is_ready": True,
            })
        return result


# --- Matchmaking Manager ---

class MatchmakingManager:
    """Manages lobby lifecycle and player assignment."""

    def __init__(self):
        self.lobbies: dict[str, LobbyState] = {}

    def create_lobby(self) -> LobbyState:
        """Create a new lobby."""
        lobby_id = str(uuid_mod.uuid4())[:8]
        lobby = LobbyState(lobby_id)
        self.lobbies[lobby_id] = lobby
        return lobby

    def find_best_lobby(self) -> LobbyState | None:
        """Find the best available lobby for a new player.
        Prefers the lobby with the most players (but not full).
        """
        available = [
            l for l in self.lobbies.values()
            if l.status in ("waiting", "countdown") and not l.is_full
        ]
        if not available:
            return None
        # Sort by player count descending (join the fullest lobby)
        available.sort(key=lambda l: l.real_player_count, reverse=True)
        return available[0]

    def join_or_create(self, user_id: str, username: str,
                       display_name: str, avatar_id: str) -> LobbyState:
        """Join the best available lobby or create a new one."""
        # Check if player is already in a lobby
        for lobby in self.lobbies.values():
            if any(p["user_id"] == user_id for p in lobby.players):
                return lobby

        lobby = self.find_best_lobby()
        if not lobby:
            lobby = self.create_lobby()

        lobby.add_player(user_id, username, display_name, avatar_id)
        return lobby

    def leave_lobby(self, user_id: str) -> LobbyState | None:
        """Remove player from their lobby. Returns lobby if found."""
        for lobby in list(self.lobbies.values()):
            if lobby.remove_player(user_id):
                # Clean up empty lobbies
                if lobby.real_player_count == 0 and lobby.status != "in_game":
                    self.remove_lobby(lobby.lobby_id)
                return lobby
        return None

    def remove_lobby(self, lobby_id: str) -> None:
        """Remove a lobby from the manager."""
        self.lobbies.pop(lobby_id, None)

    def get_lobby(self, lobby_id: str) -> LobbyState | None:
        return self.lobbies.get(lobby_id)

    def resolve_lobby(self, lobby_id: str) -> str:
        """Resolve a lobby when countdown ends.
        Returns: 'start', 'cancel', or 'waiting'.
        """
        lobby = self.get_lobby(lobby_id)
        if not lobby:
            return "cancel"

        real_count = lobby.real_player_count
        if real_count >= settings.MAX_PLAYERS:
            lobby.status = "starting"
            return "start"
        elif real_count >= settings.MIN_PLAYERS:
            lobby.fill_with_bots()
            lobby.status = "starting"
            return "start"
        else:
            lobby.status = "cancelled"
            return "cancel"


# Global matchmaking manager
matchmaking = MatchmakingManager()
