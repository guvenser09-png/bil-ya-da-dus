"""WebSocket game endpoint — full game lifecycle management.

Manages the complete 5-round game loop over WebSocket:
1. Players connect after lobby resolves into a game_id
2. Round sequence runs with timers, bot simulation, elimination
3. Eliminated players become spectators (still receive all updates)
4. Final round (slider/tahmin) determines the winner by closest estimate

Connection: ws://host/ws/game/{game_id}?token=<JWT_ACCESS_TOKEN>

Client -> Server messages:
    {"action": "submit_answer", "answer": X, "time_remaining": float}
    {"action": "emoji", "emoji": "🔥"}
    {"action": "ready"}

Server -> Client messages:
    {"type": "game_state"}         — Current snapshot on connect
    {"type": "round_start"}        — New round beginning
    {"type": "round_reveal"}       — Answers revealed, eliminations shown
    {"type": "round_transition"}   — Brief pause before next round
    {"type": "spectator_mode"}     — You were eliminated
    {"type": "game_finished"}      — Game over with final standings
    {"type": "emoji"}              — Emoji from another player
    {"type": "error"}              — Error message
"""

import asyncio
import json
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.config import settings
from app.database import async_session_factory
from app.redis_client import get_redis
from app.services.bot_service import (
    generate_bot_answer_time,
    should_bot_answer_correctly,
    should_bot_skip_answer,
)
from app.services.game_service import (
    GameEngine,
    active_games,
    create_game,
    normalize_question_type,
    remove_game,
)
from app.services.match_reward_service import grant_match_rewards
from app.services.season_service import SeasonService
from app.services.user_service import UserService
from app.utils.security import decode_token

logger = logging.getLogger(__name__)

router = APIRouter()

ALLOWED_EMOJIS = {"👏", "😂", "😱", "🔥", "💀", "❤️", "👍", "😎"}
# Tur arası bekleme: ölü zamanı kısmak için 5->3 sn (tempo iyileştirmesi).
BETWEEN_ROUNDS_PAUSE = 3  # seconds
# Erken bitirme tamponu: tüm canlı oyuncular cevaplayınca süre dolmadan turu
# kapatmadan önce kısa bir bekleme (oyuncular son anı/cevabı görsün).
EARLY_FINISH_BUFFER = 1.2  # seconds

# Ağ-gecikmesi tamponu (KÖK NEDEN DÜZELTMESİ): Tur süresi DOLDUĞUNDA, hâlâ
# cevaplamamış canlı oyuncu varsa, oyuncunun sürenin SON anında verdiği cevap
# istemci->sunucu gecikmesi yüzünden birkaç yüz ms geç ulaşabilir. Bu cevap
# end_round'dan ÖNCE işlenmezse None kalıp "doğru bildim ama elendim" hatasına
# yol açar. Bu yüzden timer dolunca reveal'dan önce kısa bir pencere daha
# bekleriz; bu sürede gelen cevap normal yolla işlenir (all_answered_event
# tetiklenirse pencere erken kapanır). Skoru etkilemez: oyuncunun bildirdiği
# time_remaining değişmez, sadece cevabın SAYILMA fırsatı korunur.
ANSWER_GRACE_PERIOD = 0.8  # seconds

# Aynı game_id için yalnızca BİR run_game döngüsü çalışsın diye koruma seti.
# lobby.py mükerrer create_task çağırsa bile ikinci çağrı hemen geri döner;
# böylece iki round-döngüsü çakışıp "erken bitiş/kaos" yaratmaz.
_running_games: set[str] = set()


# ---------------------------------------------------------------------------
# Mock questions (Week 4 — no live question DB yet)
# ---------------------------------------------------------------------------

def get_mock_questions() -> list[dict]:
    """Return 5 mock questions, one per round type."""
    return [
        {
            "id": "mock_1",
            "type": "dogru_yanlis",
            "content": "Ankara Türkiye'nin başkentidir.",
            "question": "Ankara Türkiye'nin başkentidir.",
            "options": ["Doğru", "Yanlış"],
            "correct_answer": 0,
            "time_seconds": 5,
            "image_url": None,
        },
        {
            "id": "mock_2",
            "type": "gorsel",
            "content": "Bu hangi ülkenin bayrağıdır?",
            "question": "Bu hangi ülkenin bayrağıdır?",
            "options": ["Türkiye", "Japonya", "Kanada", "İsviçre"],
            "correct_answer": 0,
            "time_seconds": 7,
            "image_url": "https://flagcdn.com/w320/tr.png",
        },
        {
            "id": "mock_3",
            "type": "karsilastirma",
            "content": "Hangisi daha kalabalık?",
            "question": "Hangisi daha kalabalık?",
            "options": ["İstanbul", "Ankara"],
            "correct_answer": 0,
            "time_seconds": 7,
            "image_url": None,
        },
        {
            "id": "mock_4",
            "type": "coktan_secmeli",
            "content": "Türkiye'nin para birimi hangisidir?",
            "question": "Türkiye'nin para birimi hangisidir?",
            "options": ["Euro", "Dolar", "Türk Lirası", "Sterlin"],
            "correct_answer": 2,
            "time_seconds": 8,
            "image_url": None,
        },
        {
            "id": "mock_5",
            "type": "tahmin",
            "content": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "question": "Türkiye'nin nüfusu kaçtır? (milyon)",
            "options": None,
            "correct_answer": 85,
            "real_answer": 85,
            "min_value": 50,
            "max_value": 150,
            "unit": "milyon",
            "time_seconds": 8,
            "image_url": None,
        },
    ]


# ---------------------------------------------------------------------------
# GameConnectionManager
# ---------------------------------------------------------------------------

class GameConnectionManager:
    """Manages active WebSocket connections for in-progress games."""

    def __init__(self):
        # user_id -> (websocket, game_id)
        self.connections: dict[str, tuple[WebSocket, str]] = {}
        # game_id -> set of active (non-eliminated) user_ids
        self.game_members: dict[str, set[str]] = {}
        # game_id -> set of eliminated spectator user_ids
        self.spectators: dict[str, set[str]] = {}
        # game_id -> asyncio.Task for the running round timer
        self.round_tasks: dict[str, asyncio.Task] = {}

    async def connect(self, user_id: str, websocket: WebSocket, game_id: str) -> None:
        """Register a new WebSocket connection for a game."""
        self.connections[user_id] = (websocket, game_id)
        self.game_members.setdefault(game_id, set()).add(user_id)

    def disconnect(self, user_id: str) -> str | None:
        """Unregister a connection. Returns the game_id the user was in."""
        if user_id not in self.connections:
            return None
        _, game_id = self.connections.pop(user_id)
        self.game_members.get(game_id, set()).discard(user_id)
        self.spectators.get(game_id, set()).discard(user_id)
        return game_id

    async def send_to_user(self, user_id: str, message: dict) -> None:
        """Send a message to a specific connected user."""
        if user_id in self.connections:
            ws, _ = self.connections[user_id]
            try:
                await ws.send_text(json.dumps(message, default=str))
            except Exception:
                pass

    async def broadcast_to_game(self, game_id: str, message: dict) -> None:
        """Send a message to ALL connected users in a game (active + spectators)."""
        data = json.dumps(message, default=str)
        all_members = (
            self.game_members.get(game_id, set()) |
            self.spectators.get(game_id, set())
        )
        for user_id in list(all_members):
            if user_id in self.connections:
                ws, _ = self.connections[user_id]
                try:
                    await ws.send_text(data)
                except Exception:
                    pass

    async def broadcast_to_active_players(self, game_id: str, message: dict) -> None:
        """Send a message only to alive (non-spectator) players."""
        data = json.dumps(message, default=str)
        for user_id in list(self.game_members.get(game_id, set())):
            if user_id in self.connections:
                ws, _ = self.connections[user_id]
                try:
                    await ws.send_text(data)
                except Exception:
                    pass

    def add_spectator(self, user_id: str, game_id: str) -> None:
        """Move a player from active to spectator."""
        self.game_members.get(game_id, set()).discard(user_id)
        self.spectators.setdefault(game_id, set()).add(user_id)

    def cleanup_game(self, game_id: str) -> None:
        """Remove all tracking data for a finished game."""
        self.game_members.pop(game_id, None)
        self.spectators.pop(game_id, None)
        task = self.round_tasks.pop(game_id, None)
        if task and not task.done():
            task.cancel()


# Global manager instance
game_manager = GameConnectionManager()


# ---------------------------------------------------------------------------
# JWT helper (WebSocket-safe — no HTTP exceptions)
# ---------------------------------------------------------------------------

def _authenticate_ws_token(token: str) -> dict | None:
    """Decode JWT token from WebSocket query param. Returns payload or None."""
    try:
        return decode_token(token, expected_type="access")
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Redis state helpers
# ---------------------------------------------------------------------------

async def _save_game_state(game_id: str, state: dict) -> None:
    """Persist game state snapshot to Redis."""
    try:
        client = await get_redis()
        await client.set(
            f"game:{game_id}:state",
            json.dumps(state, default=str),
            ex=3600,  # 1-hour TTL — games can't last longer
        )
    except Exception as exc:
        logger.warning("Redis write failed for game %s: %s", game_id, exc)


async def _load_game_state(game_id: str) -> dict | None:
    """Load game state from Redis."""
    try:
        client = await get_redis()
        raw = await client.get(f"game:{game_id}:state")
        return json.loads(raw) if raw else None
    except Exception as exc:
        logger.warning("Redis read failed for game %s: %s", game_id, exc)
        return None


def _build_state_snapshot(engine: GameEngine) -> dict:
    """Build a serializable state dict from the live GameEngine.

    Exposes the players both as a list (``players`` / ``allPlayers`` — the shape
    the mobile client expects so it can compute the remaining-player count from
    ``is_alive``) and as a user_id-keyed map (``players_by_id``) for any
    server-side / Redis consumers that prefer lookup-by-id.
    """
    players_list = []
    players_by_id = {}
    for username, p in engine.players.items():
        entry = {
            "username": username,
            "display_name": p.display_name,
            "avatar_id": p.avatar_id,
            "is_alive": p.is_alive,
            "score": p.score,
            "streak": p.streak,
            "eliminated_at_round": p.eliminated_at_round,
            "is_bot": p.is_bot,
            # Kuşanılmış kozmetikler (mobil oyuncu objesinden okur).
            "frame": p.frame,
            "name_color": p.name_color,
            "effect": p.effect,
        }
        players_list.append(entry)
        players_by_id[p.user_id or username] = entry
    return {
        "game_id": engine.game_id,
        "status": engine.status,
        "current_round": engine.current_round,
        "total_rounds": 5,
        "alive_count": engine.alive_count,
        "players": players_list,
        "allPlayers": players_list,
        "players_by_id": players_by_id,
        "started_at": engine.started_at.isoformat(),
    }


# ---------------------------------------------------------------------------
# Core game loop
# ---------------------------------------------------------------------------

def _connected_real_participant_count(game_id: str, engine: GameEngine) -> int:
    """Oyuna hâlâ bağlı (game WS açık) gerçek oyuncu sayısını döndür.

    Hem aktif (game_members) hem izleyici (spectators) bağlantıları sayılır;
    böylece elenip izleyici olan ama hâlâ açık duran bir oyuncu da bağlı kabul
    edilir. Tüm gerçek oyuncular WS'i kapatınca oyun anlamını yitirir.
    """
    connected = (
        game_manager.game_members.get(game_id, set())
        | game_manager.spectators.get(game_id, set())
    )
    real_ids = {p.user_id for p in engine.players.values() if not p.is_bot and p.user_id}
    return len(real_ids & connected)


async def _persist_game_results(game_id: str, engine: GameEngine, final: dict) -> dict[str, int]:
    """Oyun bitince GERÇEK oyuncuların istatistiklerini KALICI olarak kaydet.

    - User tablosu: games_played, games_won, total_score (BİRİKİMLİ), win_rate,
      doğru cevap sayaçları → "çok oynayan çok puan toplar" sistemi.
    - Maç sonu COIN ödülü (pay-to-win YOK): kazanan +50, ilk 3 +25, herkes +10;
      günlük 500 coin cap'i ile. Sadece gerçek oyunculara, idempotent.
    - Redis günlük/haftalık sıralama: o oyunda kazanılan puan kadar artırılır.

    Hatalar oyun akışını ASLA bozmasın diye tüm gövde try/except ile sarılı.

    Returns:
        {user_id: coins_earned} — bu maçta her gerçek oyuncunun kazandığı coin.
    """
    winner = final.get("winner") or {}
    winner_username = winner.get("username") if isinstance(winner, dict) else winner

    real_players = [
        p for p in engine.players.values() if not p.is_bot and p.user_id
    ]
    coins_earned: dict[str, int] = {}
    if not real_players:
        return coins_earned

    # --- İdempotency: bu maç daha önce ödüllendirildiyse coin tekrar verme ---
    rewards_already_granted = False
    try:
        redis = await get_redis()
        # SET NX: ilk çağrıda 1 döner; ikinci çağrıda None → zaten işlenmiş.
        first = await redis.set(
            f"match:rewarded:{game_id}", "1", nx=True, ex=24 * 3600
        )
        rewards_already_granted = first is None
    except Exception as exc:
        logger.warning("Game %s: ödül idempotency kontrolü atlandı: %s", game_id, exc)

    # --- Postgres: birikimli istatistikler ---
    try:
        async with async_session_factory() as db:
            for p in real_players:
                try:
                    await UserService.update_game_stats(
                        db,
                        user_id=p.user_id,
                        won=(p.username == winner_username),
                        score=int(p.score),
                        correct_answers=int(getattr(p, "correct_answers", 0)),
                        total_questions=int(getattr(p, "total_answers", 0)),
                    )
                except Exception as exc:  # tek oyuncu hatası diğerlerini engellemesin
                    logger.warning("Stat kaydı başarısız (user %s): %s", p.user_id, exc)

                # --- Battle Pass / Sezon puanı (pay-to-win YOK) ---
                # Sezon puanı = oyun skoru + kazanana 100 bonus + 50 katılım.
                # Ödül otomatik verilmez; oyuncu /api/season/claim ile alır.
                try:
                    season_points = (
                        int(p.score)
                        + (100 if p.username == winner_username else 0)
                        + 50
                    )
                    await SeasonService.add_points(db, p.user_id, season_points)
                except Exception as exc:  # sezon hatası stat/akışı bozmasın
                    logger.warning("Sezon puanı eklenemedi (user %s): %s", p.user_id, exc)

                # --- Aylık RANKED sezon puanı (turnuva 3x; pay-to-win YOK) ---
                # Performansa bağlı puan (skor + kazanan bonusu + katılım); turnuva
                # maçında 3x çarpan. Giriş ücreti puan VERMEZ — sadece bu maçta
                # daha hızlı tırmanma fırsatı. season_id'li → her ay sıfırlanır.
                try:
                    from app.services.tournament_service import (
                        TOURNAMENT_POINT_MULTIPLIER,
                        TournamentService,
                    )
                    ranked_points = (
                        int(p.score)
                        + (100 if p.username == winner_username else 0)
                        + 50
                    )
                    if getattr(engine, "is_tournament", False):
                        ranked_points *= TOURNAMENT_POINT_MULTIPLIER
                    await TournamentService.add_season_points(
                        db, p.user_id, ranked_points
                    )
                except Exception as exc:  # ranked sezon hatası akışı bozmasın
                    logger.warning(
                        "Ranked sezon puanı eklenemedi (user %s): %s", p.user_id, exc
                    )

            # --- Maç sonu COIN ödülü (cap'li, idempotent, sadece coin) ---
            if not rewards_already_granted:
                try:
                    ranked = sorted(
                        real_players, key=lambda pl: pl.score, reverse=True
                    )
                    ranked_user_ids = [pl.user_id for pl in ranked]
                    coins_earned = await grant_match_rewards(db, ranked_user_ids)
                except Exception as exc:
                    logger.warning(
                        "Game %s: maç coin ödülü verilemedi: %s", game_id, exc
                    )
            await db.commit()
    except Exception as exc:
        logger.warning("Game %s: istatistik kaydı başarısız: %s", game_id, exc)

    # --- Redis: günlük + haftalık sıralama (zincrby) ---
    try:
        now = datetime.now(timezone.utc)
        day_key = f"leaderboard:daily:{now.strftime('%Y%m%d')}"
        iso = now.isocalendar()
        week_key = f"leaderboard:weekly:{iso[0]}W{iso[1]:02d}"
        redis = await get_redis()
        for p in real_players:
            if p.score <= 0:
                continue
            await redis.zincrby(day_key, float(p.score), p.user_id)
            await redis.zincrby(week_key, float(p.score), p.user_id)
        # Süre sınırı: günlük 2 gün, haftalık 9 gün sonra otomatik silinir.
        await redis.expire(day_key, 2 * 24 * 3600)
        await redis.expire(week_key, 9 * 24 * 3600)
    except Exception as exc:
        logger.warning("Game %s: Redis sıralama güncellenemedi: %s", game_id, exc)

    # --- Maç sonucu anlık görüntüsü (REST /api/games/{id}/result için) ---
    # GameParticipant kalıcı kaydı tutulmadığından ve oyun motoru (active_games)
    # bitince temizlendiğinden, WS game_finished'i kaçıran kullanıcı sonucu
    # alabilsin diye sonucu Redis'e yazıyoruz. game_finished ile AYNI veriler.
    try:
        redis = await get_redis()
        leaderboard = final.get("leaderboard") or []
        # Maçta oynanan soruların özeti (mobil "soruları & doğru cevapları gör").
        # Snapshot kullanıcıdan bağımsızdır: tüm sorular + doğru cevaplar tutulur.
        questions_summary = _build_questions_summary(engine)
        # Kullanıcı-bazlı cevapları sonradan üretebilmek için round bazında
        # tüm oyuncuların cevap map'ini de saklarız (REST /result kişiselleştirir).
        answers_by_round = {
            str(r.round_number): {
                uname: {
                    "answer": a.get("answer"),
                    "correct_bool": bool(a.get("correct", a.get("winner", False))),
                }
                for uname, a in r.player_answers.items()
            }
            for r in engine.round_results
        }
        # username -> user_id eşlemesi (REST /result'ta kişiyi bulmak için).
        username_to_uid = {
            uname: p.user_id
            for uname, p in engine.players.items()
            if p.user_id
        }
        snapshot = {
            "winner": winner_username,
            "questions": questions_summary,
            "answers_by_round": answers_by_round,
            "username_to_uid": username_to_uid,
            # Oynanan toplam tur (WS game_finished ile aynı; REST my_result bunu okur).
            "total_rounds": int(final.get("total_rounds", 0)),
            "leaderboard": [
                {
                    "user_id": (
                        p.user_id if (p := engine.players.get(row["username"])) else None
                    ),
                    "username": row.get("username"),
                    "display_name": row.get("display_name"),
                    "avatar_id": row.get("avatar_id"),
                    "frame": row.get("frame"),
                    "name_color": row.get("name_color"),
                    "effect": row.get("effect"),
                    "score": int(row.get("score", 0)),
                    "correct_answers": int(row.get("correct_answers", 0)),
                    # Oyuncunun hayatta kaldığı tur sayısı = ulaştığı son tur.
                    "rounds_survived": int(row.get("rounds_survived", 0)),
                    "is_winner": bool(row.get("is_winner", False)),
                    "is_bot": bool(row.get("is_bot", False)),
                    "coins_earned": int(
                        coins_earned.get(
                            engine.players[row["username"]].user_id, 0
                        )
                    ) if row["username"] in engine.players
                    and engine.players[row["username"]].user_id else 0,
                }
                for row in leaderboard
            ],
        }
        # 24 saat saklanır (oyuncu sonuç ekranını sonra açsa bile görür).
        await redis.set(
            f"match:result:{game_id}", json.dumps(snapshot), ex=24 * 3600
        )
    except Exception as exc:
        logger.warning("Game %s: sonuç anlık görüntüsü kaydedilemedi: %s", game_id, exc)

    return coins_earned


def _build_questions_summary(engine: GameEngine) -> list[dict]:
    """Maçta OYNANAN soruların özetini üret (mobil 'soruları & doğru cevapları gör').

    Yalnızca gerçekten oynanan turlar (engine.round_results) dahil edilir; her
    soru için soru metni, tip, doğru cevap ve (varsa) şıklar döner. Bu özet
    kullanıcıdan BAĞIMSIZDIR (herkes için aynı) — kişiye özel cevaplar ayrıca
    _attach_user_answers ile eklenir.

    Dönen her öğe:
        {round, type, text, correct_answer, correct_index?, options?,
         correct_option_text?, unit?, image_url?}
    """
    summary: list[dict] = []
    for result in engine.round_results:
        q = result.question or {}
        qtype = q.get("type")
        text = q.get("question") or q.get("content") or ""
        options = q.get("options")
        item: dict = {
            "round": result.round_number,
            "type": qtype,
            "text": text,
            "correct_answer": result.correct_answer,
        }
        if q.get("image_url"):
            item["image_url"] = q.get("image_url")
        if isinstance(options, list) and options:
            item["options"] = options
            # correct_answer şıklı sorularda indekstir; metni de ekle.
            ca = result.correct_answer
            if isinstance(ca, int) and 0 <= ca < len(options):
                item["correct_index"] = ca
                item["correct_option_text"] = options[ca]
        if qtype == "tahmin":
            # Tahmin turunda correct_answer gerçek değerdir (indeks değil).
            if q.get("unit"):
                item["unit"] = q.get("unit")
            item["min_value"] = q.get("min_value")
            item["max_value"] = q.get("max_value")
        summary.append(item)
    return summary


def _attach_user_answers(questions: list[dict], engine: GameEngine, username: str | None) -> list[dict]:
    """Soru özetine bir oyuncunun kişisel cevabını ekle (your_answer, correct_bool).

    questions: _build_questions_summary çıktısı. username verilmezse/yoksa özet
    olduğu gibi (kişisel alan olmadan) döner. Cevaplar round_results'taki
    player_answers map'inden üretilir.
    """
    if not username:
        return questions
    enriched: list[dict] = []
    # round_number -> player_answers eşlemesi
    by_round = {r.round_number: r.player_answers for r in engine.round_results}
    for item in questions:
        new_item = dict(item)
        ans_map = by_round.get(item["round"], {})
        ans = ans_map.get(username)
        if ans is not None:
            new_item["your_answer"] = ans.get("answer")
            # "correct" düzenli turlarda, "winner" tahmin turunda doğruluğu verir.
            new_item["correct_bool"] = bool(
                ans.get("correct", ans.get("winner", False))
            )
        enriched.append(new_item)
    return enriched


async def _broadcast_game_state(game_id: str, engine: GameEngine) -> None:
    """Broadcast a fresh game_state snapshot to everyone in the game.

    The client relies on the is_alive flags in players/allPlayers to display
    the remaining-player count, so we push this after every elimination point.
    """
    state = _build_state_snapshot(engine)
    await game_manager.broadcast_to_game(game_id, {
        "type": "game_state",
        "game_id": game_id,
        "state": state,
        "players": state["players"],
        "allPlayers": state["allPlayers"],
        "alive_count": state["alive_count"],
        "current_round": state["current_round"],
        "total_rounds": state["total_rounds"],
    })


def _real_user_ids(engine: GameEngine) -> list[str]:
    """Motordaki gerçek (bot olmayan, user_id'si olan) oyuncuların id'leri."""
    return [
        p.user_id for p in engine.players.values()
        if not p.is_bot and p.user_id
    ]


async def _consume_tournament_tickets(engine: GameEngine) -> None:
    """Maç gerçekten başladığında turnuva biletlerini tüket (iade edilmez).

    Hata oyun akışını ASLA bozmasın diye try/except sarılı.
    """
    try:
        from app.services.tournament_service import TournamentService

        for uid in _real_user_ids(engine):
            await TournamentService.consume_ticket(uid)
    except Exception:
        logger.exception("Game %s: turnuva biletleri tüketilemedi", engine.game_id)


async def _refund_tournament_game(
    engine: GameEngine, user_ids: set[str] | None = None
) -> None:
    """Maç hiç başlamadan iptal olduğunda turnuva biletlerini iade et.

    user_ids verilmezse motordaki gerçek oyuncular kullanılır. Pending olmayan
    biletler atlanır (idempotent). Hata akışı bozmasın diye sessiz.
    """
    try:
        from app.services.tournament_service import TournamentService

        ids = list(user_ids) if user_ids else _real_user_ids(engine)
        refunded = await TournamentService.refund_pending_for_users(ids)
        if refunded:
            logger.info(
                "Game %s: maç başlamadı, %d turnuva iadesi yapıldı",
                engine.game_id, refunded,
            )
    except Exception:
        logger.exception("Game %s: turnuva iadesi başarısız", engine.game_id)


async def run_game(
    game_id: str,
    players: list[dict],
    bots: list[dict],
    questions: list[dict] | None = None,
    is_tournament: bool = False,
) -> None:
    """Execute the full 5-round game sequence.

    Called after the lobby resolves. Runs completely asynchronously;
    each round uses an asyncio.Event to allow early completion when
    all alive players have answered.
    """
    # ----------------------------------------------------------------
    # MÜKERRER BAŞLATMA KORUMASI
    # Aynı game_id için ikinci bir run_game tetiklenirse (lobby çift
    # create_task, restart, vb.) hemen geri dön. Aksi halde iki round
    # döngüsü aynı engine üzerinde yarışır → çift round_start, erken
    # game_finished, kullanıcının gördüğü "oyun patladı" durumu.
    # ----------------------------------------------------------------
    if game_id in _running_games:
        logger.warning(
            "Game %s için run_game zaten çalışıyor — mükerrer başlatma engellendi.",
            game_id,
        )
        return
    _running_games.add(game_id)
    try:
        await _run_game_inner(game_id, players, bots, questions, is_tournament)
    finally:
        _running_games.discard(game_id)


async def _run_game_inner(
    game_id: str,
    players: list[dict],
    bots: list[dict],
    questions: list[dict] | None = None,
    is_tournament: bool = False,
) -> None:
    """run_game'in asıl gövdesi (mükerrer koruma dışında çalışan kısım)."""
    if questions is None:
        # Önce DB'deki onaylı (seed'li) soruları kullan; yetersizse mock'a düş.
        # Turnuva ise ZOR havuzdan (difficulty>=eşik) seç (kolay→zor rampa yok).
        try:
            from app.database import async_session_factory
            from app.services.question_service import QuestionService
            from app.services.tournament_service import (
                NORMAL_MAX_DIFFICULTY,
                TOURNAMENT_MIN_DIFFICULTY,
            )
            # Turnuva: zor havuz (difficulty>=4). Normal: kolay/orta (difficulty<=3).
            # Tip başına yeterli soru yoksa question_service kademeli gevşetir;
            # maç ASLA iptal olmaz (mock'a düşmeden önce DB fallback'i tüketilir).
            if is_tournament:
                min_diff, max_diff = TOURNAMENT_MIN_DIFFICULTY, None
            else:
                min_diff, max_diff = None, NORMAL_MAX_DIFFICULTY
            async with async_session_factory() as db:
                questions = await QuestionService.get_game_questions_dicts(
                    db, min_difficulty=min_diff, max_difficulty=max_diff
                )
            if questions:
                logger.info(
                    "Game %s: %d soru DB'den yüklendi (tournament=%s, min=%s, max=%s)",
                    game_id, len(questions), is_tournament, min_diff, max_diff,
                )
        except Exception as e:  # pragma: no cover
            logger.warning("DB soru yüklenemedi, mock sorulara düşülüyor: %s", e)
            questions = None
        if not questions:
            questions = get_mock_questions()
            logger.info("Game %s: mock sorular kullanılıyor", game_id)

    # Create (or reuse) the engine
    if game_id not in active_games:
        engine = create_game(game_id, players, bots, is_tournament=is_tournament)
    else:
        engine = active_games[game_id]

    # Gerçek oyuncuların kuşanılmış kozmetiklerini TEK sorguda doldur (N+1 yok).
    # Botların kozmetiği zaten engine kurulumunda deterministik atandı. Bundan
    # sonraki TÜM broadcast'ler (round_start/round_end/game_state/finished) bu
    # değerleri yeniden kullanır.
    await engine.apply_real_cosmetics()

    logger.info("Game %s starting with %d players, %d bots", game_id, len(players), len(bots))

    # ----------------------------------------------------------------
    # Gerçek oyuncuların OYUN WebSocket'i bağlanana kadar bekle.
    #
    # KRİTİK: Sabit bir bekleme (eski hali: 4sn) mobil lobi->oyun geçişi +
    # WS el sıkışması daha uzun sürdüğünde 1. TURU KAÇIRTIYORDU. Round 1'i
    # kaçıran oyuncu cevap veremeden "yanlış/cevapsız" sayılıp 1. turda
    # eleniyor; sonra 2. turu izleyici olarak görüp "oyun bitti 1." sonucunu
    # alıyordu. Bu yüzden artık tüm gerçek oyuncuların game WS'i bağlanana
    # kadar (bir üst sınıra kadar) bekliyoruz.
    expected_user_ids = {
        p.user_id for p in engine.players.values()
        if not p.is_bot and p.user_id
    }
    MIN_WAIT = 2.0    # herkes anında bağlansa bile en az bu kadar bekle
    MAX_WAIT = 25.0   # bağlanmayan(lar) için sonsuza dek bekleme
    POLL = 0.25
    await asyncio.sleep(MIN_WAIT)
    waited = MIN_WAIT
    if expected_user_ids:
        while waited < MAX_WAIT:
            connected = game_manager.game_members.get(game_id, set())
            missing = expected_user_ids - connected
            if not missing:
                logger.info(
                    "Game %s: tüm gerçek oyuncular (%d) %.1fsn'de bağlandı",
                    game_id, len(expected_user_ids), waited,
                )
                break
            await asyncio.sleep(POLL)
            waited += POLL
        else:
            still_missing = expected_user_ids - game_manager.game_members.get(game_id, set())
            logger.warning(
                "Game %s: %d oyuncu %.0fsn içinde bağlanmadı (%s); yine de başlıyoruz",
                game_id, len(still_missing), MAX_WAIT, still_missing,
            )

        # HİÇBİR gerçek oyuncu MAX_WAIT içinde bağlanmadıysa oyunu iptal et:
        # botlarla boş oyun oynamak anlamsız ve sadece kaynak/mesaj israfı.
        connected_now = game_manager.game_members.get(game_id, set())
        if expected_user_ids and not (expected_user_ids & connected_now):
            logger.warning(
                "Game %s: hiçbir gerçek oyuncu bağlanmadı — oyun iptal ediliyor.",
                game_id,
            )
            # Money-safe: maç HİÇ başlamadı (hiç gerçek oyuncu bağlanmadı) →
            # turnuva giriş ücretlerini iade et.
            if getattr(engine, "is_tournament", False):
                await _refund_tournament_game(engine, expected_user_ids)
            game_manager.cleanup_game(game_id)
            remove_game(game_id)
            return
    # Bağlantılar yerleşsin diye küçük bir tampon (round_start kaçmasın).
    await asyncio.sleep(0.75)

    # Maç GERÇEKTEN başlıyor (en az bir gerçek oyuncu bağlı). Turnuva ise
    # giriş biletlerini TÜKET → artık iade edilmez (sink olarak yandı).
    if getattr(engine, "is_tournament", False):
        await _consume_tournament_tickets(engine)

    # Notify everyone: game is live
    await game_manager.broadcast_to_game(game_id, {
        "type": "game_started",
        "game_id": game_id,
        "total_rounds": 5,
        "alive_count": engine.alive_count,
    })

    # ----------------------------------------------------------------
    # ROUND LOOP
    # ----------------------------------------------------------------
    for round_idx in range(5):
        question = questions[round_idx]
        # KÖK NEDEN: DB enum'u BÜYÜK HARF döndürür ('TAHMIN', ...). Tipi küçük
        # harfe normalize et ki "tahmin" karşılaştırmaları (correct_answer vs
        # real_answer seçimi, bot cevap üretimi) sağlam olsun. start_round /
        # end_round da aynı kanonik tipi kullanır → widget ↔ skorlama eşleşir.
        q_type = normalize_question_type(question) or "coktan_secmeli"
        question["type"] = q_type
        correct_answer = question.get("correct_answer") if q_type != "tahmin" else question.get("real_answer")

        # --- Start round ---
        round_start_msg = engine.start_round(question)
        await _save_game_state(game_id, _build_state_snapshot(engine))
        await game_manager.broadcast_to_game(game_id, round_start_msg)

        # KÖK NEDEN DÜZELTMESİ: Sunucu tur-zamanlayıcısı TEK kaynaktan —
        # engine.get_round_config()["time"] — beslenmeli. start_round istemciye
        # bu config süresini (turnuvada uzatılmış: 10/14/14/16/16) gönderiyor;
        # eski kod ise sunucu timer'ını DB sorusunun question["time_seconds"]
        # değerine bağlıyordu. İkisi farklı olunca (özellikle turnuvada) istemci
        # 14sn sayarken sunucu 7sn'de turu kapatıyor, oyuncu ekrandaki süre
        # dolmadan cevabı None kalıp ELENİYORDU. Artık ikisi de config'ten gelir
        # → istemci sayacı ile sunucu cevap penceresi BİREBİR aynı.
        time_limit = engine.get_round_config()["time"]
        # Event fires when all alive human players have answered
        all_answered_event = asyncio.Event()

        # Track which real players we are waiting for
        alive_user_ids: set[str] = set()
        for p in engine.alive_players:
            if not p.is_bot and p.user_id:
                alive_user_ids.add(p.user_id)
        answered_user_ids: set[str] = set()

        # Store the event and answer tracking on engine so the WS handler can access them
        engine._round_event = all_answered_event           # type: ignore[attr-defined]
        engine._awaiting_answers = alive_user_ids.copy()  # type: ignore[attr-defined]
        engine._received_answers = answered_user_ids       # type: ignore[attr-defined]

        # His için: bu turda hiç cevap vermeyecek (pas geçen) botların adları.
        # simulate_bot_answers'ın bunları force-fill etmemesi için engine'e konur.
        bots_skipping_round: set[str] = set()
        engine._bots_skipping_round = bots_skipping_round  # type: ignore[attr-defined]

        # --- Schedule bot answers ---
        async def _schedule_bot_answers(eng: GameEngine, q: dict, ca: object) -> None:
            """Simulate bots answering asynchronously at realistic delays."""
            config = eng.get_round_config()
            for player in list(eng.alive_players):
                if not player.is_bot:
                    continue
                # His için: bazı botlar bu turda hiç cevap vermesin (kararsız).
                # Pas geçen bot uyumadan atlanır; turun sonunda cevapsız sayılır.
                if should_bot_skip_answer(player.bot_difficulty):
                    bots_skipping_round.add(player.username)
                    continue
                # Doğal dağılımlı gecikme (turun cevap penceresi içinde).
                delay = generate_bot_answer_time(
                    player.bot_difficulty, time_limit=float(config["time"])
                )
                delay = min(delay, config["time"] - 0.2)
                await asyncio.sleep(delay)
                if not player.is_alive or player.current_answer is not None:
                    continue
                # Use the engine's built-in simulation for a single bot
                if q["type"] == "tahmin":
                    import random
                    real = q.get("real_answer", 500)
                    min_val = q.get("min_value", 0)
                    max_val = q.get("max_value", 1000)
                    spread = {"easy": 0.3, "medium": 0.15, "hard": 0.07}.get(player.bot_difficulty, 0.15)
                    offset = random.gauss(0, spread * (max_val - min_val))
                    guess = max(min_val, min(max_val, real + offset))
                    player.current_answer = round(guess, 1)
                else:
                    is_correct = should_bot_answer_correctly(player.bot_difficulty, eng.current_round)
                    if is_correct:
                        player.current_answer = ca
                    else:
                        import random as _rnd
                        options = q.get("options") or []
                        if isinstance(options, list) and len(options) > 1:
                            wrong = [i for i in range(len(options)) if i != ca]
                            player.current_answer = _rnd.choice(wrong) if wrong else 0
                        else:
                            player.current_answer = 1 - ca if ca in (0, 1) else 0
                player.answer_time = max(0.0, float(config["time"]) - delay)

        bot_task = asyncio.create_task(_schedule_bot_answers(engine, question, correct_answer))

        # --- Tur süresi VEYA erken bitiş (hangisi önce) ---
        # TEMPO: Tüm canlı (bot olmayan) oyuncular cevapladıysa/elendiyse turu
        # süre dolmadan kapat. all_answered_event, _handle_submit_answer içinde
        # tüm beklenen gerçek oyuncular cevap verince set edilir. Erken bitişte
        # küçük bir tampon bekleyip reveal'a geçeriz (oyuncular son anı görsün).
        #
        # Canlı gerçek oyuncu YOKSA (hepsi bot / herkes elendi) erken bitiş
        # devreye girmez; mevcut "tam süre bekle" davranışı korunur.
        # İdempotent: tur yalnızca BİR kez kapanır — iki yol (timer / event)
        # ortak `asyncio.wait` ile yarıştırılır, hangisi önce biterse o kazanır;
        # döngü tek seferlik akışla devam ettiği için çift-kapanma olmaz.
        if alive_user_ids:
            timer_task = asyncio.create_task(asyncio.sleep(float(time_limit)))
            event_task = asyncio.create_task(all_answered_event.wait())
            done, pending = await asyncio.wait(
                {timer_task, event_task},
                return_when=asyncio.FIRST_COMPLETED,
            )
            early_finish = event_task in done and timer_task not in done
            for t in pending:
                t.cancel()
            for t in pending:
                try:
                    await t
                except asyncio.CancelledError:
                    pass
            if early_finish:
                # Tüm canlı oyuncular cevapladı: kısa tampon sonrası reveal.
                logger.info(
                    "Game %s tur %d: tüm canlı oyuncular cevapladı, erken bitiş.",
                    game_id, engine.current_round,
                )
                await asyncio.sleep(EARLY_FINISH_BUFFER)
            else:
                # Süre doldu ama hâlâ cevaplamamış canlı oyuncu var olabilir.
                # Ağ-gecikmesi tamponu: oyuncunun son-an cevabı yolda olabilir.
                # Beklenen tüm cevaplar zaten geldiyse beklemeye gerek yok.
                received: set[str] = getattr(engine, "_received_answers", set())
                if not alive_user_ids.issubset(received):
                    grace_task = asyncio.create_task(all_answered_event.wait())
                    try:
                        await asyncio.wait_for(grace_task, timeout=ANSWER_GRACE_PERIOD)
                    except asyncio.TimeoutError:
                        grace_task.cancel()
                        try:
                            await grace_task
                        except asyncio.CancelledError:
                            pass
        else:
            # Canlı gerçek oyuncu yok (hepsi bot): tam süre beklenir.
            await asyncio.sleep(float(time_limit))

        # Ensure bots have answered (cancel remaining, force fill with timeout answers)
        bot_task.cancel()
        try:
            await bot_task
        except asyncio.CancelledError:
            pass

        # Fill any bots that still haven't answered (timer ran out mid-think)
        engine.simulate_bot_answers(correct_answer, question)

        # --- Gerçek oyuncu kaldı mı? ---
        # Tur ortasında tüm gerçek oyuncular oyundan ayrıldıysa (WS kapandı)
        # botlarla devam edip kimsenin görmeyeceği bir game_finished üretmenin
        # anlamı yok. Oyunu sessizce sonlandır ve temizle. Bu, kullanıcının
        # "oyundan çıkıp yeni oyun başlatınca eski oyun hâlâ dönüyor" sorununu
        # (eski game_finished'in yanlış yere sızması) engeller.
        if _connected_real_participant_count(game_id, engine) == 0:
            logger.info(
                "Game %s: tur %d sonunda bağlı gerçek oyuncu kalmadı — oyun temizleniyor.",
                game_id, engine.current_round,
            )
            game_manager.cleanup_game(game_id)
            remove_game(game_id)
            return

        # --- End round & compute eliminations ---
        result = engine.end_round(correct_answer, question)
        round_msg = engine.get_round_end_message(result)

        # Rename "round_end" -> "round_reveal" to match the WS contract spec
        reveal_msg = dict(round_msg)
        reveal_msg["type"] = "round_reveal"

        await game_manager.broadcast_to_game(game_id, reveal_msg)

        # --- Move eliminated players to spectator mode ---
        for username in result.eliminated:
            p = engine.players.get(username)
            if p and p.user_id and not p.is_bot:
                game_manager.add_spectator(p.user_id, game_id)
                await game_manager.send_to_user(p.user_id, {
                    "type": "spectator_mode",
                    "game_id": game_id,
                    "message": "Elendi! Diğer oyuncuları izliyorsunuz.",
                    "eliminated_at_round": result.round_number,
                })

        await _save_game_state(game_id, _build_state_snapshot(engine))

        # --- Push an authoritative game_state so the client's remaining-player
        #     count reflects this round's eliminations immediately. ---
        await _broadcast_game_state(game_id, engine)

        # --- Battle-royale early stop ---
        # Game is over the moment 0 or 1 players remain (last one standing wins).
        # No point running the remaining rounds.
        if engine.alive_count <= 1:
            break

        # --- Between-rounds pause (skip after final round) ---
        if round_idx < 4:
            # Transition message (next round number is round_idx + 2 because round_idx is 0-based)
            next_round = round_idx + 2
            await asyncio.sleep(BETWEEN_ROUNDS_PAUSE)
            transition_players = engine.players_summary()
            await game_manager.broadcast_to_game(game_id, {
                "type": "round_transition",
                "game_id": game_id,
                "next_round": next_round,
                "alive_count": engine.alive_count,
                "players": transition_players,
                "allPlayers": transition_players,
            })

    # ----------------------------------------------------------------
    # GAME FINISHED
    # ----------------------------------------------------------------
    # Son turun reveal'ı (kazananı belirleyen eleme) sonuç ekranına geçmeden
    # önce ekranda kalsın ki oyuncular son düşenleri net görebilsin.
    await asyncio.sleep(BETWEEN_ROUNDS_PAUSE)

    final = engine.finish_game()

    # Build estimates list for slider round (last played round)
    all_estimates: list[dict] = []
    if engine.round_results:
        last_result = engine.round_results[-1]
        if last_result.question.get("type") == "tahmin":
            real_ans = last_result.correct_answer
            for username, ans_data in last_result.player_answers.items():
                p = engine.players.get(username)
                all_estimates.append({
                    "username": username,
                    "display_name": p.display_name if p else username,
                    "estimate": ans_data.get("answer"),
                    "distance": ans_data.get("distance"),
                    "winner": ans_data.get("winner", False),
                })

    # Birikimli puan + sıralama + maç COIN ödülü (cap'li, idempotent) önce
    # işlenir ki kazanılan coin (coins_earned) kişisel game_finished mesajına
    # eklenebilsin. Bu fonksiyon hata fırlatmaz (gövdesi try/except sarılı).
    coins_earned = await _persist_game_results(game_id, engine, final)

    # Maçta oynanan soruların özeti (mobil "soruları & doğru cevapları gör").
    # Genel mesaja kullanıcıdan bağımsız özet konur; aşağıda her gerçek
    # oyuncuya kişisel cevapları (your_answer/correct_bool) eklenir.
    questions_summary = _build_questions_summary(engine)

    game_finished_msg = {
        "type": "game_finished",
        "game_id": game_id,
        "winner": final["winner"],
        "final_standings": final["leaderboard"],
        "total_rounds": final["total_rounds"],
        "duration_seconds": final["duration_seconds"],
        "questions": questions_summary,
    }
    if all_estimates:
        game_finished_msg["all_estimates"] = all_estimates

    # Send personalised score to each connected real player.
    # KRİTİK: Her gerçek oyuncuya game_finished YALNIZCA BİR KEZ gitmeli.
    # Eskiden hem send_to_user (kişisel) hem broadcast_to_game (genel) ikisi de
    # gerçek oyunculara ulaşıyordu → MÜKERRER game_finished → istemcide ikinci
    # sonuç ekranı/"oyun patladı" karışıklığı. Kişisel mesaj gönderdiklerimizi
    # işaretleyip genel yayını yalnızca KALANLARA (kişisel alamayanlara) yap.
    personally_notified: set[str] = set()
    for p in engine.players.values():
        if p.is_bot or not p.user_id:
            continue
        personal_msg = dict(game_finished_msg)
        personal_msg["your_score"] = p.score
        # Bu maçta kazanılan coin (cap sonrası gerçek miktar; 0 olabilir).
        personal_msg["coins_earned"] = int(coins_earned.get(p.user_id, 0))
        # Kişiye özel cevaplar: her soruya your_answer + correct_bool ekle.
        personal_msg["questions"] = _attach_user_answers(
            questions_summary, engine, p.username
        )
        await game_manager.send_to_user(p.user_id, personal_msg)
        personally_notified.add(p.user_id)

    # Kişisel mesaj almayan (ör. user_id eşleşmesi kopmuş) bağlı üyelere/izleyicilere
    # genel game_finished gönder — ama kişisel alanları ATLA ki mükerrer gitmesin.
    remaining = (
        game_manager.game_members.get(game_id, set())
        | game_manager.spectators.get(game_id, set())
    ) - personally_notified
    for uid in remaining:
        await game_manager.send_to_user(uid, game_finished_msg)

    logger.info("Game %s finished. Winner: %s", game_id, final["winner"].get("username"))

    # Cleanup
    game_manager.cleanup_game(game_id)
    remove_game(game_id)


# ---------------------------------------------------------------------------
# WebSocket endpoint
# ---------------------------------------------------------------------------

@router.websocket("/game/{game_id}")
async def game_websocket(websocket: WebSocket, game_id: str):
    """WebSocket endpoint for in-progress game communication.

    Connection: ws://host/ws/game/{game_id}?token=<JWT_ACCESS_TOKEN>
    """
    # --- Authentication ---
    token = websocket.query_params.get("token")
    if not token:
        await websocket.close(code=4001, reason="Token gerekli.")
        return

    payload = _authenticate_ws_token(token)
    if not payload:
        await websocket.close(code=4001, reason="Geçersiz token.")
        return

    user_id: str = payload.get("sub", "")
    if not user_id:
        await websocket.close(code=4001, reason="Geçersiz token payload.")
        return

    # --- Verify player is a game participant ---
    engine = active_games.get(game_id)
    if not engine:
        await websocket.close(code=4004, reason="Oyun bulunamadı.")
        return

    # Check the player is listed (by user_id)
    is_participant = any(
        p.user_id == user_id for p in engine.players.values() if not p.is_bot
    )
    if not is_participant:
        await websocket.close(code=4003, reason="Bu oyunun katılımcısı değilsiniz.")
        return

    await websocket.accept()
    await game_manager.connect(user_id, websocket, game_id)

    # --- Send current game state snapshot ---
    state = _build_state_snapshot(engine)
    await websocket.send_text(json.dumps({
        "type": "game_state",
        "game_id": game_id,
        "state": state,
        # Surface the player list at the top level too so the client can read
        # players/allPlayers (with up-to-date is_alive) without unwrapping.
        "players": state["players"],
        "allPlayers": state["allPlayers"],
        "alive_count": state["alive_count"],
        "current_round": state["current_round"],
        "total_rounds": state["total_rounds"],
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }, default=str))

    # --- Message loop ---
    try:
        while True:
            raw = await websocket.receive_text()
            try:
                message = json.loads(raw)
            except json.JSONDecodeError:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": "Geçersiz JSON formatı.",
                }))
                continue

            # İstemci mesajları `type` anahtarıyla gönderir
            # ({"type": "submit_answer", ...}); eski kod ise `action`
            # bekliyordu. Geriye dönük uyumluluk için her ikisini de kabul et.
            action = message.get("action") or message.get("type")

            if action == "submit_answer":
                _handle_submit_answer(engine, user_id, message)

            elif action == "lock_answer":
                # Slider kilitleme istemci tarafında yönetilir; sunucu için
                # ek işlem gerekmez. Mevcut cevabı kesinleştirme amaçlı no-op.
                await websocket.send_text(json.dumps({
                    "type": "lock_ack",
                    "message": "Cevap kilitlendi.",
                }))

            elif action == "emoji":
                emoji = message.get("emoji", "")
                if emoji in ALLOWED_EMOJIS:
                    # Find username for this user_id
                    sender_username = next(
                        (p.username for p in engine.players.values() if p.user_id == user_id),
                        "oyuncu",
                    )
                    await game_manager.broadcast_to_game(game_id, {
                        "type": "emoji",
                        "user_id": user_id,
                        "username": sender_username,
                        "emoji": emoji,
                    })

            elif action == "ready":
                # Acknowledgement — no server action needed but send confirmation
                await websocket.send_text(json.dumps({
                    "type": "ready_ack",
                    "message": "Hazır.",
                }))

            else:
                await websocket.send_text(json.dumps({
                    "type": "error",
                    "message": f"Bilinmeyen action: {action}",
                }))

    except WebSocketDisconnect:
        logger.info("User %s disconnected from game %s", user_id, game_id)
    except Exception as exc:
        logger.error("Game WS error user=%s game=%s: %s", user_id, game_id, exc)
    finally:
        game_manager.disconnect(user_id)


def _handle_submit_answer(engine: GameEngine, user_id: str, message: dict) -> None:
    """Process a submitted answer from a human player.

    Also signals the all_answered_event when every alive human has answered.
    """
    # Find player by user_id
    player = next(
        (p for p in engine.players.values() if p.user_id == user_id and not p.is_bot),
        None,
    )
    answer = message.get("answer")
    if not player:
        return

    time_remaining = float(message.get("time_remaining", 0.0))

    accepted = engine.submit_answer(player.username, answer, time_remaining)
    if not accepted:
        return  # Already answered or not alive

    # Mark this user as answered
    received: set[str] = getattr(engine, "_received_answers", set())
    received.add(user_id)

    awaiting: set[str] = getattr(engine, "_awaiting_answers", set())
    event: asyncio.Event | None = getattr(engine, "_round_event", None)

    if event and awaiting and awaiting.issubset(received):
        event.set()  # All human players have answered — end round early
