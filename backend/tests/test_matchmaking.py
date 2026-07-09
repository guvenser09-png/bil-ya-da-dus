"""Tests for matchmaking service."""

import pytest

from app.services.matchmaking_service import (
    LobbyState,
    MatchmakingManager,
)


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
        """Lobby with <5 real players but ≥1 now starts (AAS fills bots).

        Under the Adaptive Threshold System a lobby is cancelled only when
        there are zero real players.  Even 3 real players are valid — the
        remaining 17 slots are filled with bots and the game starts.
        """
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        for i in range(3):
            lobby.add_player(f"u{i}", f"player{i}", f"Player {i}", "default_01")

        result = mm.resolve_lobby(lobby.lobby_id)
        assert result == "start"
        assert lobby.total_count == 20  # 3 real + 17 bots

    def test_resolve_zero_players_cancels(self):
        """A lobby with no real players at all is cancelled."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()

        result = mm.resolve_lobby(lobby.lobby_id)
        assert result == "cancel"
        assert lobby.status == "cancelled"

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

    def test_lobby_never_cancelled_with_one_player(self):
        """When only 1 real player is present the lobby should start, not cancel.

        AAS guarantees: as long as ≥ 1 real player exists, bots fill the rest
        and the game begins.
        """
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        lobby.add_player("u1", "player1", "Player 1", "default_01")

        result = mm.resolve_lobby(lobby.lobby_id, min_real_players=5)

        assert result == "start"
        assert lobby.status == "starting"
        assert lobby.total_count == 20  # 1 real + 19 bots

    def test_bot_join_schedule_spread(self):
        """Bot join offsets must all fall within [0, 18) seconds."""
        lobby = LobbyState("sched-test")
        for i in range(3):
            lobby.add_player(f"u{i}", f"p{i}", f"Player {i}", "default_01")

        bots_needed = 17  # 20 - 3
        offsets = lobby.schedule_bot_joins(total_bots=bots_needed, window_seconds=18.0)

        assert len(offsets) == bots_needed
        # Must be sorted
        assert offsets == sorted(offsets)
        # All offsets within window (90 % threshold used internally)
        assert all(0.0 <= o < 18.0 for o in offsets)
        # Stored on the lobby object
        assert lobby.bot_join_schedule == offsets

    def test_min_real_players_respected(self):
        """When min_real=2 but only 1 real player is present the lobby still
        starts — bots fill the gap. Cancel only fires at 0 real players."""
        mm = MatchmakingManager()
        lobby = mm.create_lobby()
        lobby.add_player("u1", "solo_player", "Solo Player", "default_01")

        # Simulate AAS resolving a high threshold (min_real=2) for this lobby
        result = mm.resolve_lobby(lobby.lobby_id, min_real_players=2)

        assert result == "start"
        # AAS threshold is recorded on the lobby for observability
        assert lobby.min_real_players == 2
        # Game can still proceed: bots topped up the rest
        assert lobby.total_count == 20


class TestBotMixOverrides:
    """İlk-maç senaryosu + anti-tilt bot karışım override'ları."""

    def test_first_match_mix_gradual_and_fill(self):
        """first_match karışımı: ilk 11 bot ≈ 9 easy + 2 medium + 0 hard.

        Hem kademeli ekleme (add_one_bot) hem toplu doldurma (fill_with_bots)
        AYNI merdiveni kullanmalı.
        """
        lobby = LobbyState("first-match-1")
        lobby.add_player("u_new", "yeni_oyuncu", "Yeni Oyuncu", "default_01")
        lobby.set_bot_mix("first_match")

        # Kademeli görünür ekleme (ws/lobby._bot_fill_loop'un kullandığı yol)
        for _ in range(5):
            lobby.add_one_bot()
        # Kalanı resolve anındaki toplu doldurma tamamlar (fill_with_bots)
        lobby.fill_with_bots()

        # Karışım her iki yolda da korunur; hiçbir slotta hard bot olmamalı
        assert all(b["difficulty"] != "hard" for b in lobby.bots)

        first_11 = lobby.bots[:11]
        easy = sum(1 for b in first_11 if b["difficulty"] == "easy")
        medium = sum(1 for b in first_11 if b["difficulty"] == "medium")
        hard = sum(1 for b in first_11 if b["difficulty"] == "hard")

        assert easy == 9, f"9 easy bekleniyordu, {easy} geldi"
        assert medium == 2, f"2 medium bekleniyordu, {medium} geldi"
        assert hard == 0, f"first_match karışımında hard bot olmamalı, {hard} geldi"

    def test_priority_first_match_beats_anti_tilt(self):
        """Öncelik sırası: ilk-maç > anti-tilt > varsayılan.

        Hangi sırada tetiklenirse tetiklensin first_match kazanmalı; ayrıca
        önceden eklenmiş botların zorlukları yeni merdivene göre güncellenmeli.
        """
        # anti-tilt önce, ilk-maç sonra → first_match kazanır
        lobby = LobbyState("prio-1")
        lobby.add_player("u1", "p1", "P1", "default_01")
        for _ in range(6):  # varsayılan karışımla bot eklenmiş olsun
            lobby.add_one_bot()
        lobby.set_bot_mix("easy_heavy")
        lobby.set_bot_mix("first_match")
        assert lobby.bot_mix == "first_match"
        # Mevcut botlar yeniden dağıtıldı: first_match'te hard bot kalmaz
        assert all(b["difficulty"] != "hard" for b in lobby.bots)

        # ilk-maç önce, anti-tilt sonra → first_match korunur (düşürme yok)
        lobby2 = LobbyState("prio-2")
        lobby2.set_bot_mix("first_match")
        lobby2.set_bot_mix("easy_heavy")
        assert lobby2.bot_mix == "first_match"

        # Tek başına anti-tilt → easy_heavy uygulanır (ilk 11: 9e + 2m + 0h)
        lobby3 = LobbyState("prio-3")
        lobby3.add_player("u3", "p3", "P3", "default_01")
        lobby3.set_bot_mix("easy_heavy")
        while len(lobby3.bots) < 11:
            lobby3.add_one_bot()
        easy = sum(1 for b in lobby3.bots if b["difficulty"] == "easy")
        assert lobby3.bot_mix == "easy_heavy"
        assert easy >= 8, f"easy_heavy karışımında ilk 11 botun ~%80'i easy olmalı ({easy} easy)"

    def test_tournament_lobby_ignores_overrides(self):
        """Turnuva lobisinde override NO-OP: varsayılan karışım korunur."""
        lobby = LobbyState("tourn-1", is_tournament=True)
        lobby.add_player("u1", "p1", "P1", "default_01")
        lobby.set_bot_mix("first_match")
        lobby.set_bot_mix("easy_heavy")
        assert lobby.bot_mix == "default"

        lobby.fill_with_bots()
        # Varsayılan merdiven (4e+4m+4h) → hard botlar mevcut olmalı
        assert any(b["difficulty"] == "hard" for b in lobby.bots)

    def test_generous_guess_spread_widened(self):
        """İlk-maç senaryosunda bot slider sapması genişletilir (easy %30→%45)."""
        from app.services.bot_service import bot_guess_spread

        for diff in ("easy", "medium", "hard"):
            assert bot_guess_spread(diff, generous=True) > bot_guess_spread(diff)
        assert bot_guess_spread("easy") == 0.30
        assert bot_guess_spread("easy", generous=True) == 0.45
