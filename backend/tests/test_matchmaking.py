"""Tests for matchmaking service."""

import pytest

from app.services.matchmaking_service import LobbyState, MatchmakingManager


class TestLobbyState:
    """Test lobby state management."""

    def test_add_player(self):
        """Adding a player increases count."""
        lobby = LobbyState("test-1")
        result = lobby.add_player("u1", "player1", "Player 1", "default_01")
        assert result is True
        assert lobby.real_player_count == 1

    def test_add_duplicate_player(self):
        """Cannot add same player twice."""
        lobby = LobbyState("test-1")
        lobby.add_player("u1", "player1", "Player 1", "default_01")
        result = lobby.add_player("u1", "player1", "Player 1", "default_01")
        assert result is False
        assert lobby.real_player_count == 1

    def test_remove_player(self):
        """Removing a player decreases count."""
        lobby = LobbyState("test-1")
        lobby.add_player("u1", "player1", "Player 1", "default_01")
        result = lobby.remove_player("u1")
        assert result is True
        assert lobby.real_player_count == 0

    def test_fill_with_bots(self):
        """Bots fill remaining slots up to MAX_PLAYERS."""
        lobby = LobbyState("test-1")
        for i in range(5):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")

        bots_added = lobby.fill_with_bots()
        assert bots_added == 15  # 20 - 5 = 15 bots
        assert lobby.total_count == 20

    def test_is_full(self):
        """Lobby reports full at MAX_PLAYERS."""
        lobby = LobbyState("test-1")
        for i in range(20):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")
        assert lobby.is_full is True

    def test_player_list_for_client(self):
        """Client player list includes bots without revealing them."""
        lobby = LobbyState("test-1")
        lobby.add_player("u1", "player1", "Player 1", "default_01")
        lobby.bots.append({"bot_name": "bot1", "difficulty": "easy", "avatar_id": "default_02"})

        player_list = lobby.player_list_for_client()
        assert len(player_list) == 2
        # Bot should look like a player
        assert all("is_ready" in p for p in player_list)


class TestMatchmakingManager:
    """Test matchmaking logic."""

    def test_create_lobby(self):
        """Creating a lobby adds it to the manager."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        assert lobby.lobby_id in mm.lobbies
        assert lobby.status == "waiting"

    def test_join_or_create_new(self):
        """First player creates a new lobby."""
        mm = MatchmakingManager()
        lobby = mm.join_or_create("u1", "player1", "Player 1", "default_01")
        assert lobby.real_player_count == 1

    def test_join_existing_lobby(self):
        """Second player joins the existing lobby."""
        mm = MatchmakingManager()
        lobby1 = mm.join_or_create("u1", "player1", "Player 1", "default_01")
        lobby2 = mm.join_or_create("u2", "player2", "Player 2", "default_01")
        assert lobby1.lobby_id == lobby2.lobby_id
        assert lobby2.real_player_count == 2

    def test_leave_lobby(self):
        """Player can leave their lobby."""
        mm = MatchmakingManager()
        mm.join_or_create("u1", "player1", "Player 1", "default_01")
        mm.join_or_create("u2", "player2", "Player 2", "default_01")

        lobby = mm.leave_lobby("u1")
        assert lobby is not None
        assert lobby.real_player_count == 1

    def test_resolve_with_enough_players(self):
        """Lobby with 5+ players starts with bots."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        for i in range(6):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")

        result = mm.resolve_lobby(lobby.lobby_id)
        assert result == "start"
        assert lobby.total_count == 20  # 6 real + 14 bots

    def test_resolve_not_enough_players(self):
        """Lobby with <5 players gets cancelled."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        for i in range(3):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")

        result = mm.resolve_lobby(lobby.lobby_id)
        assert result == "cancel"

    def test_resolve_full_lobby(self):
        """Full lobby starts immediately."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        for i in range(20):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")

        result = mm.resolve_lobby(lobby.lobby_id)
        assert result == "start"
        assert len(lobby.bots) == 0  # No bots needed

    def test_player_already_in_lobby(self):
        """Same player joining again returns existing lobby."""
        mm = MatchmakingManager()
        lobby1 = mm.join_or_create("u1", "player1", "Player 1", "default_01")
        lobby2 = mm.join_or_create("u1", "player1", "Player 1", "default_01")
        assert lobby1.lobby_id == lobby2.lobby_id
        assert lobby2.real_player_count == 1
