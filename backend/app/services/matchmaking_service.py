"""Matchmaking service — lobby creation, player assignment, countdown.

Lobby lifecycle (from CLAUDE.md Section 2.1):
1. Every 20 seconds a new lobby opens
2. Multiple lobbies can run in parallel
3. Player joins the lobby with the most free slots
4. Live counter: "Oyuncu aranıyor... 7/20"
5. When countdown ends:
   - 20 players → game starts immediately
   - 5-19 real players → fill with bots, game starts
   - <5 real players → fill with bots, game starts (AAS: still start with ≥1 real player)
   - 0 real players  → cancel

AAS integration: resolve_lobby accepts an optional min_real_players parameter
(computed by cap_service.get_min_real_players). Even when real_count < min_real,
the lobby is never cancelled as long as at least 1 real player is present — we
simply fill with bots and start.

All lobby state is stored in Redis for real-time access.
"""

import random
import uuid as uuid_mod
from datetime import datetime, timezone
from typing import Any

from app.config import settings
from app.redis_client import get_redis
from app.services.bot_service import generate_bot_name

# Botlar için 3D katalog karakter id'leri (mobil characters.dart ile aynı).
BOT_AVATARS = [
    "robot", "alien", "ghost", "cat_face", "dog_face", "fox", "panda",
    "lion", "tiger", "frog", "penguin", "alien_monster", "flying_saucer",
    "rocket", "octopus", "dragon_face", "dragon", "ogre", "goblin",
    "unicorn", "owl", "smiling_face_with_sunglasses", "nerd_face",
    "cowboy_hat_face", "clown_face",
]
# 12 kişilik lobiye göre: 4 easy + 4 medium + 4 hard (11 bot + 1 gerçek tipik).
_BOT_DIFFICULTIES = ["easy"] * 4 + ["medium"] * 4 + ["hard"] * 4

# --- İlk-maç senaryosu + anti-tilt bot karışım override'ları ---
# İlk-maç eşiği: lobide toplam oynanmış maçı bu sayının ALTINDA olan en az bir
# GERÇEK oyuncu varsa bot karışımı kolaylaştırılır (sadece normal eşleşme
# havuzu; turnuva ve özel oda HARİÇ).
FIRST_MATCH_MAX_GAMES = 3

# İlk-maç merdiveni: 11 bot varsayımıyla ~9 easy + 2 medium + 0 hard.
# Botlar kademeli eklenirken index sırasına göre zorluk alır; 12. slot da easy
# kalır (oran korunur, hard hiç girmez).
_FIRST_MATCH_DIFFICULTIES = ["easy"] * 9 + ["medium"] * 2 + ["easy"] * 1
# Anti-tilt merdiveni (3 üst üste kayıp): ~%80 easy + %15 medium + %5 hard.
_EASY_HEAVY_DIFFICULTIES = ["easy"] * 9 + ["medium"] * 2 + ["hard"] * 1

# Karışım adı → zorluk merdiveni. fill_with_bots ve add_one_bot AYNI merdiveni
# kullanır; böylece kademeli görünür ekleme de override'a uyar.
_MIX_LADDERS: dict[str, list[str]] = {
    "default": _BOT_DIFFICULTIES,
    "first_match": _FIRST_MATCH_DIFFICULTIES,
    "easy_heavy": _EASY_HEAVY_DIFFICULTIES,
}
# Öncelik sırası: ilk-maç senaryosu > anti-tilt > varsayılan karışım.
# (İkisi birden tetiklenirse ilk-maç kazanır.)
_MIX_PRIORITY: dict[str, int] = {"default": 0, "easy_heavy": 1, "first_match": 2}


def _bot_cosmetics(bot_name: str) -> dict[str, Any]:
    """Bota deterministik (bot adı seed'li) görsel kozmetik döner.

    cosmetics_service ile aynı mantık — aynı bot adı her yerde aynı kozmetiği
    alır (lobi ve oyun motoru tutarlı). Pay-to-win YOK; sadece vitrin.
    """
    from app.services.cosmetics_service import CosmeticsService

    return CosmeticsService.cosmetics_for_bot(bot_name)


# ---------------------------------------------------------------------------
# Lobby Data Structures
# ---------------------------------------------------------------------------

class LobbyState:
    """In-memory representation of a lobby's state."""

    def __init__(self, lobby_id: str, is_tournament: bool = False):
        self.lobby_id = lobby_id
        # Turnuva lobisi mi? Turnuva maçında sorular ZOR seçilir ve ranked sezon
        # puanı 3x yazılır (game engine bu bayrağı okur). Normal lobi davranışı
        # DEĞİŞMEZ (is_tournament=False).
        self.is_tournament = is_tournament
        self.players: list[dict[str, Any]] = []  # [{user_id, username, display_name, avatar_id}]
        self.bots: list[dict[str, Any]] = []     # [{bot_name, difficulty, avatar_id}]
        self.created_at = datetime.now(timezone.utc)
        self.created_at_timestamp: float = self.created_at.timestamp()
        self.countdown_seconds = settings.LOBBY_TIMEOUT_SECONDS
        self.status = "waiting"  # waiting, countdown, starting, cancelled, in_game
        self.game_id: str | None = None

        # AAS integration
        self.min_real_players: int = 1

        # Bot karışım override'ı: "default" | "easy_heavy" (anti-tilt) |
        # "first_match" (ilk-maç senaryosu). set_bot_mix ile öncelik sırasına
        # göre yükseltilir; turnuva lobisinde daima "default" kalır.
        self.bot_mix: str = "default"

        # Timestamps (seconds-from-lobby-creation) at which each bot "visibly joins"
        self.bot_join_schedule: list[float] = []

    @property
    def real_player_count(self) -> int:
        return len(self.players)

    @property
    def total_count(self) -> int:
        return len(self.players) + len(self.bots)

    @property
    def is_full(self) -> bool:
        return self.real_player_count >= settings.MAX_PLAYERS

    def add_player(
        self,
        user_id: str,
        username: str,
        display_name: str,
        avatar_id: str,
        cosmetics: dict[str, Any] | None = None,
    ) -> bool:
        """Add a real player to the lobby.

        cosmetics: {"frame", "name_color", "effect"} — kuşanılmış kozmetikler.
        Lobi oyuncu listelerinde (vitrin) gösterilir; None ise boş geçilir.

        Returns:
            True if the player was added, False if the lobby is full or the
            player is already present.
        """
        if self.is_full:
            return False
        if any(p["user_id"] == user_id for p in self.players):
            return False
        cos = cosmetics or {}
        self.players.append(
            {
                "user_id": user_id,
                "username": username,
                "display_name": display_name,
                "avatar_id": avatar_id,
                "frame": cos.get("frame"),
                "name_color": cos.get("name_color"),
                "effect": cos.get("effect"),
            }
        )
        return True

    def remove_player(self, user_id: str) -> bool:
        """Remove a player from the lobby.

        Returns:
            True if the player was found and removed.
        """
        before = len(self.players)
        self.players = [p for p in self.players if p["user_id"] != user_id]
        return len(self.players) < before

    def _bot_difficulty_ladder(self) -> list[str]:
        """Aktif karışıma (bot_mix) göre zorluk merdivenini döndür."""
        return _MIX_LADDERS.get(self.bot_mix, _BOT_DIFFICULTIES)

    def _bot_difficulty_for_index(self, index: int) -> str:
        """index'inci botun zorluğunu aktif merdivene göre döndür.

        Varsayılan karışımda ESKİ davranış korunur (merdiven biterse son
        eleman, yani "hard"). Override karışımlarında merdiven MODULO ile
        sarılır ki 12'den büyük lobilerde de kolay ağırlıklı ORAN korunsun
        (clamp edilseydi 12+ botların hepsi merdivenin son elemanı olurdu).
        """
        ladder = self._bot_difficulty_ladder()
        if self.bot_mix == "default":
            return ladder[min(index, len(ladder) - 1)]
        return ladder[index % len(ladder)]

    def set_bot_mix(self, mix: str) -> None:
        """Bot karışım override'ı uygula (öncelik: first_match > easy_heavy > default).

        - Turnuva lobisinde NO-OP (senaryolar sadece normal eşleşme havuzu için).
        - Daha yüksek veya eşit öncelikli bir karışım zaten aktifse düşürmez.
        - Önceden eklenmiş botların zorlukları yeni merdivene göre yeniden
          atanır (isim/avatar değişmez — zorluk sunucu içi gizli bilgidir).
        """
        if self.is_tournament or mix not in _MIX_LADDERS:
            return
        if _MIX_PRIORITY.get(mix, 0) <= _MIX_PRIORITY.get(self.bot_mix, 0):
            return
        self.bot_mix = mix
        for i, bot in enumerate(self.bots):
            bot["difficulty"] = self._bot_difficulty_for_index(i)

    def fill_with_bots(self) -> int:
        """Fill remaining slots with bots.

        Returns:
            Number of bots added.
        """
        used_names: set[str] = {p.get("username", "") for p in self.players}
        used_names.update(b["bot_name"] for b in self.bots)

        bots_needed = settings.MAX_PLAYERS - self.total_count
        bots_added = 0

        for i in range(bots_needed):
            name = generate_bot_name()
            attempts = 0
            while name in used_names and attempts < 50:
                name = generate_bot_name()
                attempts += 1

            difficulty = self._bot_difficulty_for_index(len(self.bots))
            self.bots.append(
                {
                    "bot_name": name,
                    "difficulty": difficulty,
                    "avatar_id": random.choice(BOT_AVATARS),
                    **_bot_cosmetics(name),
                }
            )
            used_names.add(name)
            bots_added += 1

        return bots_added

    def add_one_bot(self) -> dict[str, Any] | None:
        """Tek bir bot ekler (countdown sırasında görünür doldurma için).

        Lobi doluysa (``total_count >= MAX_PLAYERS``) None döner.
        """
        if self.total_count >= settings.MAX_PLAYERS:
            return None
        used_names = {p.get("username", "") for p in self.players}
        used_names.update(b["bot_name"] for b in self.bots)
        name = generate_bot_name()
        attempts = 0
        while name in used_names and attempts < 50:
            name = generate_bot_name()
            attempts += 1
        bot = {
            "bot_name": name,
            "difficulty": self._bot_difficulty_for_index(len(self.bots)),
            "avatar_id": random.choice(BOT_AVATARS),
            **_bot_cosmetics(name),
        }
        self.bots.append(bot)
        return bot

    def schedule_bot_joins(
        self,
        total_bots: int,
        window_seconds: float = 18.0,
    ) -> list[float]:
        """Spread bot join events over window_seconds so the lobby feels alive.

        Bots appear to join one-by-one at random intervals within the window.
        The last 2 seconds of the countdown are left empty so the UI can show
        the final count cleanly before the game starts.

        Args:
            total_bots: How many bots will eventually fill the lobby.
            window_seconds: Duration (s) to spread joins over. Defaults to 18 s.

        Returns:
            Sorted list of relative offsets (seconds from now) when each bot
            should "visibly join" the lobby. Also stores the result in
            ``self.bot_join_schedule``.
        """
        if total_bots <= 0:
            self.bot_join_schedule = []
            return []

        offsets: list[float] = []
        for _ in range(total_bots):
            # Random offset within [0, window_seconds) with slight clustering
            # toward the first 80 % of the window for a natural feel
            offset = random.uniform(0.0, window_seconds * 0.9)
            offsets.append(round(offset, 2))

        offsets.sort()
        self.bot_join_schedule = offsets
        return offsets

    def to_dict(self) -> dict[str, Any]:
        """Serialize lobby state for Redis / WebSocket broadcast."""
        return {
            "lobby_id": self.lobby_id,
            "players": self.players,
            "bots": [
                {"bot_name": b["bot_name"], "avatar_id": b["avatar_id"]}
                for b in self.bots
            ],
            "real_player_count": self.real_player_count,
            "total_count": self.total_count,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "created_at_timestamp": self.created_at_timestamp,
            "game_id": self.game_id,
            "min_real_players": self.min_real_players,
            "bot_join_schedule": self.bot_join_schedule,
            "is_tournament": self.is_tournament,
        }

    def player_list_for_client(self) -> list[dict[str, Any]]:
        """Get combined player list for clients (bots appear as regular players)."""
        result: list[dict[str, Any]] = []
        for p in self.players:
            result.append(
                {
                    "username": p["username"],
                    "display_name": p["display_name"],
                    "avatar_id": p["avatar_id"],
                    "is_ready": True,
                    # Kuşanılmış kozmetikler (mobil oyuncu objesinden okur).
                    "frame": p.get("frame"),
                    "name_color": p.get("name_color"),
                    "effect": p.get("effect"),
                }
            )
        for b in self.bots:
            result.append(
                {
                    "username": b["bot_name"],
                    "display_name": b["bot_name"],
                    "avatar_id": b["avatar_id"],
                    "is_ready": True,
                    "frame": b.get("frame"),
                    "name_color": b.get("name_color"),
                    "effect": b.get("effect"),
                }
            )
        return result


# ---------------------------------------------------------------------------
# Matchmaking Manager
# ---------------------------------------------------------------------------

class MatchmakingManager:
    """Manages lobby lifecycle and player assignment."""

    def __init__(self) -> None:
        self.lobbies: dict[str, LobbyState] = {}

    def create_lobby(self, is_tournament: bool = False) -> LobbyState:
        """Create a new lobby and register it with the manager."""
        lobby_id = str(uuid_mod.uuid4())[:8]
        lobby = LobbyState(lobby_id, is_tournament=is_tournament)
        self.lobbies[lobby_id] = lobby
        return lobby

    def find_best_lobby(self, is_tournament: bool = False) -> LobbyState | None:
        """Find the best available lobby for a new player.

        Prefers the lobby with the most real players that is not yet full.
        Turnuva ve normal oyuncular AYRI havuzlarda eşleşir (is_tournament filtresi).
        """
        available = [
            lob
            for lob in self.lobbies.values()
            if lob.status in ("waiting", "countdown")
            and not lob.is_full
            and lob.is_tournament == is_tournament
        ]
        if not available:
            return None
        available.sort(key=lambda lob: lob.real_player_count, reverse=True)
        return available[0]

    def join_or_create(
        self,
        user_id: str,
        username: str,
        display_name: str,
        avatar_id: str,
        cosmetics: dict[str, Any] | None = None,
        is_tournament: bool = False,
    ) -> LobbyState:
        """Join the best available lobby or create a new one.

        If the player is already in a lobby, that lobby is returned.
        cosmetics: kuşanılmış kozmetikler (frame/name_color/effect).
        is_tournament: True ise yalnızca turnuva lobileriyle eşleşir.
        """
        for lobby in self.lobbies.values():
            if any(p["user_id"] == user_id for p in lobby.players):
                return lobby

        lobby = self.find_best_lobby(is_tournament=is_tournament)
        if not lobby:
            lobby = self.create_lobby(is_tournament=is_tournament)

        lobby.add_player(user_id, username, display_name, avatar_id, cosmetics)
        return lobby

    def leave_lobby(self, user_id: str) -> LobbyState | None:
        """Remove a player from their current lobby.

        Cleans up empty lobbies automatically.

        Returns:
            The lobby the player was in, or None if not found.
        """
        for lobby in list(self.lobbies.values()):
            if lobby.remove_player(user_id):
                if lobby.real_player_count == 0 and lobby.status != "in_game":
                    self.remove_lobby(lobby.lobby_id)
                return lobby
        return None

    def remove_lobby(self, lobby_id: str) -> None:
        """Remove a lobby from the manager."""
        self.lobbies.pop(lobby_id, None)

    def get_lobby(self, lobby_id: str) -> LobbyState | None:
        """Return the lobby with the given ID, or None."""
        return self.lobbies.get(lobby_id)

    def resolve_lobby(
        self,
        lobby_id: str,
        min_real_players: int = 1,
    ) -> str:
        """Resolve a lobby when the countdown ends.

        With AAS the lobby is NEVER cancelled as long as at least one real
        player is present — we simply fill remaining slots with bots and start.
        A cancel is only issued when there are zero real players.

        Args:
            lobby_id: ID of the lobby to resolve.
            min_real_players: Minimum real-player threshold from AAS. Currently
                used to set ``lobby.min_real_players`` for observability, but
                does NOT cause a cancel when unmet — the lobby still starts.

        Returns:
            ``"start"`` if the game should begin, ``"cancel"`` if there are no
            real players at all.
        """
        lobby = self.get_lobby(lobby_id)
        if not lobby:
            return "cancel"

        # Record the AAS-derived threshold for logging / analytics
        lobby.min_real_players = min_real_players

        real_count = lobby.real_player_count

        if real_count == 0:
            # Nothing to play — genuinely cancel
            lobby.status = "cancelled"
            return "cancel"

        if real_count >= settings.MAX_PLAYERS:
            # Already full — no bots needed
            lobby.status = "starting"
            return "start"

        # Fill remaining slots with bots (covers both 1-4 and 5-19 real players)
        lobby.fill_with_bots()
        lobby.status = "starting"
        return "start"

    def schedule_natural_bot_joins(self, lobby_id: str) -> list[float]:
        """Calculate and store when bots should visibly appear in the lobby UI.

        Spreads bot join events over 18 seconds with natural random variation.
        The last 2 seconds before game start are kept bot-join-free so the UI
        can render the final state cleanly.

        Args:
            lobby_id: ID of the lobby.

        Returns:
            Sorted list of seconds-from-now offsets, one per bot. Empty list
            if the lobby does not exist or has no bots.
        """
        lobby = self.get_lobby(lobby_id)
        if not lobby:
            return []

        bots_needed = settings.MAX_PLAYERS - lobby.real_player_count
        if bots_needed <= 0:
            lobby.bot_join_schedule = []
            return []

        return lobby.schedule_bot_joins(total_bots=bots_needed, window_seconds=18.0)


# Global matchmaking manager (shared across the process)
matchmaking = MatchmakingManager()
