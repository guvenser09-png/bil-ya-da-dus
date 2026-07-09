"""Game engine — core game loop, round management, elimination logic.

Manages the entire game lifecycle from CLAUDE.md Section 1:
- 5 rounds with different question types
- Player elimination each round (wrong answers fall)
- Final round: slider estimation
- Score calculation and winner determination
- Bot behavior integration

Round structure (eleme rampası — kolaydan zora):
| Round | Type              | Time | Difficulty | Elimination        |
|-------|-------------------|------|------------|-------------------|
| 1     | Multiple choice   | 9s   | Very easy  | Wrong answers      |
| 2     | True/False        | 7s   | Easy       | Wrong answers      |
| 3     | Visual            | 9s   | Medium     | Wrong answers      |
| 4     | Comparison        | 9s   | Med-hard   | Wrong answers      |
| 5     | Slider estimation | 10s  | Intuition  | Closest wins       |

Kalkan (🛡️) mekaniği:
- Her oyuncu (botlar DAHİL — kimse kimin bot olduğunu bilmez) maça 1 Kalkan
  ile başlar.
- Tur 1-4'te yanlış cevap veren oyuncunun Kalkanı varsa elenmek yerine Kalkan
  KIRILIR, oyuncu hayatta kalır (o turdan puan ALMAZ, streak sıfırlanır).
- İkinci yanlış = normal eleme. Final (tahmin) turunda Kalkan GEÇERSİZ.
- "Herkes yanlışsa kimse elenmez" kuralı ÖNCE uygulanır: kimse elenmeyecekse
  kalkan da kırılmaz.
"""

import asyncio
import random
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.bot_service import (
    bot_guess_spread,
    generate_bot_answer_time,
    should_bot_answer_correctly,
)
from app.services.score_service import calculate_game_score, calculate_round_score


# --- Round Configuration ---

# ELEME RAMPASI: ilk tur artık kolay 4 şıklı ISINMA sorusu (eski dogru_yanlis
# açılışı 50/50 yazı-tura infazıydı). Tipler kolaydan zora sıralanır; difficulty
# alanı 1-5 rampasıdır (bilgilendirme amaçlı — soru havuzu filtresi
# tournament_service.NORMAL_MAX_DIFFICULTY / TOURNAMENT_MIN_DIFFICULTY ile
# yönetilir, bu alan o filtreyi ETKİLEMEZ).
ROUND_CONFIG = [
    {"round": 1, "type": "coktan_secmeli",  "time": 9,  "difficulty": 1},
    {"round": 2, "type": "dogru_yanlis",    "time": 7,  "difficulty": 2},
    {"round": 3, "type": "gorsel",          "time": 9,  "difficulty": 3},
    {"round": 4, "type": "karsilastirma",   "time": 9,  "difficulty": 4},
    {"round": 5, "type": "tahmin",          "time": 10, "difficulty": 5},
]

# TURNUVA tur süreleri (KÖK NEDEN DÜZELTMESİ).
#
# Turnuva soruları ZOR havuzdan (difficulty 4-5) seçilir. Normal maçın kısa
# süreleri (5/7/7/8/8) zor bir soruyu OKUYUP cevaplamaya yetmiyordu: gerçek
# oyuncu cevabı bilse bile süre dolup cevap None kalıyor (ya da ağ gecikmesiyle
# cevap turun kapanmasından sonra ulaşıyor) → yanlış sayılıp ELENİYOR; reveal
# doğru cevabı gösterdiği için "doğru biliyordum ama elendim" şikayeti oluşuyor;
# elenince sonraki tur izleyici → şık seçemiyor. Çözüm: turnuvada cömert süre.
#
# Tek kaynak: get_round_config() turnuvada bu süreleri döndürür; start_round'un
# istemciye yolladığı time_seconds DA, run_game'deki sunucu tur-zamanlayıcısı DA
# aynı config["time"]'tan beslenir → istemci sayacı ile sunucu penceresi eşleşir.
TOURNAMENT_ROUND_CONFIG = [
    {"round": 1, "type": "coktan_secmeli",  "time": 16, "difficulty": 1},
    {"round": 2, "type": "dogru_yanlis",    "time": 12, "difficulty": 2},
    {"round": 3, "type": "gorsel",          "time": 16, "difficulty": 3},
    {"round": 4, "type": "karsilastirma",   "time": 16, "difficulty": 4},
    {"round": 5, "type": "tahmin",          "time": 18, "difficulty": 5},
]

# Geçerli soru tipleri (küçük harf, kanonik biçim). Slider/tahmin tek başına;
# diğerleri şıklı (options) sorular.
VALID_QUESTION_TYPES = {
    "dogru_yanlis", "gorsel", "karsilastirma", "coktan_secmeli", "tahmin",
}


def normalize_question_type(question: dict | None) -> str | None:
    """Bir soru dict'inin tipini KÜÇÜK HARF kanonik biçime indirger.

    DB enum'u büyük harf isimle ('TAHMIN','DOGRU_YANLIS', ...) ya da bazı
    yollarda QuestionType üyesi/değeri olarak gelebilir. Tüm karşılaştırmalar
    (widget tipi, regular vs estimation skorlama, line-800 correct_answer
    seçimi) bu kanonik biçime dayanmalı ki büyük/küçük harf uyuşmazlığı
    "doğru cevap → yanlış/eleme" hatasına yol açmasın.
    """
    if not question:
        return None
    raw = question.get("type")
    if raw is None:
        return None
    # QuestionType enum üyesi ise .value (zaten küçük harf) al.
    val = getattr(raw, "value", raw)
    s = str(val).strip().lower()
    return s or None


# --- Data Classes ---

@dataclass
class PlayerState:
    """Tracks a player's state during a game."""
    user_id: str | None  # None for bots
    username: str
    display_name: str
    avatar_id: str
    is_bot: bool = False
    bot_difficulty: str = "medium"
    # Kuşanılmış kozmetikler (görsel; mobil oyuncu objesinden frame/name_color/
    # effect anahtarlarıyla okur). Gerçek oyuncularda DB'den, botlarda
    # deterministik atanır. None = kozmetik yok.
    frame: str | None = None
    name_color: str | None = None
    effect: str | None = None
    is_alive: bool = True
    # KALKAN (🛡️): Her oyuncu (bot DAHİL — tutarlılık şart, kimse kimin bot
    # olduğunu bilmiyor) maça 1 kalkanla başlar. Tur 1-4'te ilk yanlışta
    # elenmek yerine kalkan kırılır; finalde (tahmin) geçersiz.
    shields: int = 1
    # HAYALET MODU (👻): elenen GERÇEK oyuncu izlerken cevap vermeye devam
    # edebilir. Hayalet cevaplar elemeye/skora/kazanana ETKİSİZDİR; yalnızca
    # bu sayaç artar ve maç sonunda küçük altın ödülüne çevrilir
    # (doğru başına +5, üst sınır match_reward_service.GHOST_GOLD_MAX).
    ghost_correct: int = 0
    # ŞAMPİYON BAHSİ (🎯): elenen oyuncunun "şampiyon olur" dediği username.
    # Tek seferlik, değiştirilemez. None = bahis yok. Tutarsa maç sonunda
    # +BET_REWARD altın (aynı idempotent ödül akışında, günlük cap dahil).
    champion_bet: str | None = None
    eliminated_at_round: int | None = None
    score: int = 0
    round_scores: list[int] = field(default_factory=list)
    streak: int = 0
    correct_answers: int = 0
    total_answers: int = 0
    current_answer: Any = None
    answer_time: float | None = None


@dataclass
class RoundResult:
    """Result of a single round."""
    round_number: int
    question: dict
    correct_answer: Any
    player_answers: dict[str, dict]  # username -> {answer, time, correct, score}
    eliminated: list[str]  # usernames that were eliminated
    survivors: list[str]   # usernames that survived
    # Bu tur KALKANIYLA kurtulan (yanlış cevapladı ama elenmedi) oyuncular.
    shield_saved: list[str] = field(default_factory=list)
    # HAYALET cevap sonuçları: {username: {answer, correct}}. Elenmiş
    # oyuncuların gölge cevapları — results'a KARIŞMAZ, elemeye etkisizdir.
    ghost_results: dict[str, dict] = field(default_factory=dict)


class GameEngine:
    """Manages a single game's lifecycle."""

    def __init__(
        self,
        game_id: str,
        players: list[dict],
        bots: list[dict],
        is_tournament: bool = False,
    ):
        self.game_id = game_id
        # Turnuva maçı mı? Maç sonu ranked sezon puanı 3x yazılır (pay-to-win YOK;
        # performansa bağlı). Soru seçimi de zorlu havuzdan yapılır. Normal maçta
        # False → davranış değişmez.
        self.is_tournament = is_tournament
        self.status = "waiting"  # waiting, round_active, round_end, finished
        self.current_round = 0
        self.round_results: list[RoundResult] = []
        self.started_at = datetime.now(timezone.utc)
        self.ended_at: datetime | None = None
        self.winner: PlayerState | None = None

        # Initialize player states
        self.players: dict[str, PlayerState] = {}
        from app.services.cosmetics_service import CosmeticsService

        for p in players:
            uid = p.get("user_id", str(uuid_mod.uuid4()))
            self.players[p["username"]] = PlayerState(
                user_id=uid,
                username=p["username"],
                display_name=p.get("display_name", p["username"]),
                avatar_id=p.get("avatar_id", "default_01"),
                is_bot=False,
                # Kozmetikler lobby tarafından player dict'ine konmuşsa kullan;
                # yoksa oyun başında apply_real_cosmetics ile DB'den doldurulur.
                frame=p.get("frame"),
                name_color=p.get("name_color"),
                effect=p.get("effect"),
            )
        for b in bots:
            bot_cos = CosmeticsService.cosmetics_for_bot(b["bot_name"])
            self.players[b["bot_name"]] = PlayerState(
                user_id=None,
                username=b["bot_name"],
                display_name=b["bot_name"],
                avatar_id=b.get("avatar_id", "default_01"),
                is_bot=True,
                bot_difficulty=b.get("difficulty", "medium"),
                frame=bot_cos["frame"],
                name_color=bot_cos["name_color"],
                effect=bot_cos["effect"],
            )

    async def apply_real_cosmetics(self) -> None:
        """Gerçek oyuncuların kuşanılmış kozmetiklerini TEK sorguda doldur.

        N+1 önlemek için tüm gerçek oyuncuların user_id'leri tek
        ``WHERE id IN (...)`` sorgusuyla çekilir ve PlayerState'lere yazılır.
        Oyun başında bir kez çağrılır; sonraki tüm broadcast'ler bu değerleri
        yeniden kullanır. Hata oyun akışını bozmasın diye sessizce geçilir.
        """
        from app.database import async_session_factory
        from app.services.cosmetics_service import CosmeticsService

        real_ids = [
            p.user_id for p in self.players.values()
            if not p.is_bot and p.user_id
        ]
        if not real_ids:
            return
        try:
            async with async_session_factory() as db:
                equipped = await CosmeticsService.equipped_for_users(db, real_ids)
        except Exception:
            return
        for p in self.players.values():
            if p.is_bot or not p.user_id:
                continue
            cos = equipped.get(str(p.user_id))
            if cos:
                p.frame = cos.get("frame")
                p.name_color = cos.get("name_color")
                p.effect = cos.get("effect")

    @property
    def alive_players(self) -> list[PlayerState]:
        """Get list of players still in the game."""
        return [p for p in self.players.values() if p.is_alive]

    @property
    def alive_real_players(self) -> list[PlayerState]:
        """Get list of real (non-bot) players still alive."""
        return [p for p in self.alive_players if not p.is_bot]

    @property
    def alive_count(self) -> int:
        return len(self.alive_players)

    def get_round_config(self) -> dict:
        """Get configuration for the current round.

        Turnuva maçında (is_tournament=True) zor soru havuzu için CÖMERT süreli
        TOURNAMENT_ROUND_CONFIG döner; normal maçta süreler DEĞİŞMEZ. Bu, hem
        start_round'un istemciye yolladığı time_seconds'ı hem run_game'deki
        sunucu tur-zamanlayıcısını TEK kaynaktan besler → istemci sayacı ile
        sunucu cevap penceresi her zaman aynı uzunlukta olur.
        """
        config = TOURNAMENT_ROUND_CONFIG if self.is_tournament else ROUND_CONFIG
        if 0 < self.current_round <= 5:
            return config[self.current_round - 1]
        return config[0]

    def start_round(self, question: dict) -> dict:
        """Start a new round. Returns round info for clients."""
        self.current_round += 1
        self.status = "round_active"

        config = self.get_round_config()

        # KÖK NEDEN DÜZELTMESİ: İstemciye giden widget tipi (tip/round_type),
        # SERVİS EDİLEN sorunun GERÇEK tipinden gelmelidir — sabit ROUND_CONFIG'ten
        # değil. Soru havuzunda tipe uygun soru kalmayınca question_service
        # FARKLI tipte bir soru fallback'ler; eski kod yine de config tipini
        # (ör. "tahmin") gönderiyordu → istemci slider gösterip kullanıcı 4-şıklı
        # soruyu doğru cevaplayamıyor, ya da tam tersi → "doğru cevap → yanlış/eleme".
        # Tipi her zaman küçük harfe normalize ediyoruz (DB enum'u büyük harf
        # döndürüyor: 'TAHMIN','DOGRU_YANLIS', ...).
        effective_type = normalize_question_type(question)
        if effective_type not in VALID_QUESTION_TYPES:
            effective_type = config["type"]
        # end_round'un regular/estimation kararı ile tutarlı kalsın diye bu turun
        # efektif tipini engine'de sakla (end_round aynı değeri kullanır).
        self._round_effective_type = effective_type  # type: ignore[attr-defined]

        # Reset answers for this round
        for p in self.alive_players:
            p.current_answer = None
            p.answer_time = None

        # HAYALET MODU: elenmiş oyuncuların bu tura ait gölge cevapları.
        # Her tur başında sıfırlanır; end_round'da değerlendirilir.
        self._ghost_answers: dict[str, dict] = {}  # type: ignore[attr-defined]

        # Prepare question for clients (hide correct answer)
        # Use "tip" key to match Flutter client and CLAUDE.md spec
        question_text = question.get("question", question.get("content", ""))
        client_question = {
            "id": question.get("id", f"q_{self.current_round}"),
            "tip": effective_type,
            "question": question_text,
            "content": question_text,
            "soru": question_text,
            "options": question.get("options"),
            "secenekler": question.get("options"),
            "image_url": question.get("image_url"),
            "sure_saniye": config["time"],
            "time_seconds": config["time"],
        }

        # For estimation round, add slider config
        if effective_type == "tahmin":
            client_question["min_value"] = question.get("min_value", 0)
            client_question["max_value"] = question.get("max_value", 1000)
            client_question["unit"] = question.get("unit", "")

        return {
            "type": "round_start",
            "game_id": self.game_id,
            "round": self.current_round,
            "total_rounds": 5,
            "round_type": effective_type,
            "question": client_question,
            "alive_count": self.alive_count,
            "time_seconds": config["time"],
            "players": [
                {
                    "username": p.username,
                    "display_name": p.display_name,
                    "avatar_id": p.avatar_id,
                    "is_alive": p.is_alive,
                    "score": p.score,
                    "is_bot": p.is_bot,
                    # Kalan kalkan sayısı (mobil 🛡️ rozetini bundan çizer).
                    "shields": p.shields,
                    "frame": p.frame,
                    "name_color": p.name_color,
                    "effect": p.effect,
                }
                for p in self.players.values()
            ],
        }

    def submit_answer(self, username: str, answer: Any, time_remaining: float) -> bool:
        """Submit a player's answer. Returns True if accepted."""
        player = self.players.get(username)
        if not player or not player.is_alive or player.current_answer is not None:
            return False

        player.current_answer = answer
        player.answer_time = time_remaining
        return True

    def submit_ghost_answer(
        self, username: str, answer: Any, time_remaining: float
    ) -> bool:
        """HAYALET MODU: elenmiş GERÇEK oyuncunun gölge cevabını kaydet.

        Elemeye/skora/kazanana ETKİSİZDİR — yalnızca end_round'da
        değerlendirilip ghost_correct sayacını artırır (maç sonunda küçük
        altın ödülü). Tur başına tek cevap; sadece tur aktifken kabul edilir.
        """
        player = self.players.get(username)
        if not player or player.is_alive or player.is_bot:
            return False
        if self.status != "round_active":
            return False
        ghosts: dict[str, dict] | None = getattr(self, "_ghost_answers", None)
        if ghosts is None or username in ghosts:
            return False
        ghosts[username] = {"answer": answer, "time_remaining": time_remaining}
        return True

    def _resolve_ghost_answers(self, is_correct_fn) -> dict[str, dict]:
        """Bu turun hayalet cevaplarını değerlendir; sayaçları güncelle.

        Returns:
            {username: {answer, correct}} — reveal'da kişiye gösterilecek
            gölge sonuçlar (results map'ine KARIŞMAZ).
        """
        ghosts: dict[str, dict] = getattr(self, "_ghost_answers", None) or {}
        out: dict[str, dict] = {}
        for username, data in ghosts.items():
            player = self.players.get(username)
            if not player or player.is_alive:
                continue
            try:
                correct = bool(is_correct_fn(data.get("answer")))
            except Exception:
                correct = False
            if correct:
                player.ghost_correct += 1
            out[username] = {"answer": data.get("answer"), "correct": correct}
        return out

    def place_champion_bet(
        self, username: str, target_username: str
    ) -> tuple[bool, str]:
        """ŞAMPİYON BAHSİ: elenmiş oyuncu hayatta kalan birine bahis koyar.

        Tek seferlik ve değiştirilemez; yalnızca elenmiş GERÇEK oyuncudan,
        yalnızca HAYATTA olan bir oyuncuya. Tutarsa maç sonunda +BET_REWARD
        altın (idempotent ödül akışında, günlük cap dahil).

        Returns:
            (kabul_edildi, hata_mesajı) — kabulde hata mesajı boş string.
        """
        player = self.players.get(username)
        if not player or player.is_bot:
            return False, "Oyuncu bulunamadı."
        if player.is_alive:
            return False, "Bahis sadece elendikten sonra yapılabilir."
        if player.champion_bet is not None:
            return False, "Bahsini zaten yaptın — değiştirilemez."
        if self.status == "finished":
            return False, "Oyun bitti — bahis yapılamaz."
        target = self.players.get(target_username)
        if not target or not target.is_alive:
            return False, "Sadece hayatta olan bir oyuncuya bahis yapabilirsin."
        player.champion_bet = target_username
        return True, ""

    def simulate_bot_answers(self, correct_answer: Any, question: dict) -> None:
        """Generate answers for all bots still alive.

        Bu tur "pas geçen" (his için hiç cevap vermeyecek) botlar
        _bots_skipping_round içinde işaretliyse force-fill EDİLMEZ; böylece
        cevapsız kalıp turda doğal "süre doldu" davranışı sergilerler.
        """
        config = self.get_round_config()
        skipping: set[str] = getattr(self, "_bots_skipping_round", set())

        for player in self.alive_players:
            if not player.is_bot or player.current_answer is not None:
                continue
            if player.username in skipping:
                continue

            answer_time = generate_bot_answer_time()

            if config["type"] == "tahmin":
                # For estimation: generate a guess near the real answer
                real = question.get("real_answer", 500)
                min_val = question.get("min_value", 0)
                max_val = question.get("max_value", 1000)

                # Harder bots guess closer (ilk-maç senaryosunda sapma GENİŞ)
                spread = bot_guess_spread(
                    player.bot_difficulty,
                    generous=getattr(self, "generous_bot_guesses", False),
                )

                offset = random.gauss(0, spread * (max_val - min_val))
                guess = max(min_val, min(max_val, real + offset))
                player.current_answer = round(guess, 1)
            else:
                # For regular rounds
                is_correct = should_bot_answer_correctly(
                    player.bot_difficulty, self.current_round
                )
                if is_correct:
                    player.current_answer = correct_answer
                else:
                    # Pick a wrong answer
                    options = question.get("options", {})
                    if isinstance(options, list) and len(options) > 1:
                        wrong_indices = [
                            i for i in range(len(options))
                            if i != correct_answer
                        ]
                        player.current_answer = random.choice(wrong_indices) if wrong_indices else 0
                    else:
                        # True/false: opposite of correct
                        player.current_answer = 1 - correct_answer if correct_answer in (0, 1) else 0

            player.answer_time = max(0, config["time"] - answer_time)

    def end_round(self, correct_answer: Any, question: dict) -> RoundResult:
        """End the current round, calculate scores, and eliminate players."""
        eliminated = []
        survivors = []
        player_answers = {}

        # KÖK NEDEN DÜZELTMESİ: regular vs estimation skorlama kararı, SERVİS
        # EDİLEN sorunun GERÇEK tipine dayanmalı — sabit ROUND_CONFIG'e değil.
        # start_round bu turun efektif (gerçek) tipini sakladı; aynısını kullan
        # ki istemciye gösterilen widget ile skorlama yolu HER ZAMAN eşleşsin.
        # Aksi halde örn. bir 'tahmin' sorusu 'gorsel' turunda servis edilince
        # estimation yerine "answer == real_answer" indeks karşılaştırması
        # yapılıp herkes yanlış sayılırdı.
        effective_type = getattr(self, "_round_effective_type", None)
        if effective_type not in VALID_QUESTION_TYPES:
            effective_type = normalize_question_type(question)
        if effective_type not in VALID_QUESTION_TYPES:
            effective_type = self.get_round_config()["type"]

        if effective_type == "tahmin":
            # Final round: closest to real answer wins
            return self._end_estimation_round(correct_answer, question)

        # Regular round: wrong answers are eliminated (kalkan yoksa)
        shield_saved: list[str] = []
        wrong_players: list[str] = []

        for player in self.alive_players:
            answer = player.current_answer
            time_remaining = player.answer_time or 0
            is_correct = answer == correct_answer

            player.total_answers += 1

            if is_correct:
                player.streak += 1
                player.correct_answers += 1
                round_score = calculate_round_score(
                    time_remaining_seconds=time_remaining,
                    is_correct=True,
                    streak_count=player.streak,
                )
            else:
                # Yanlış cevap: puan YOK, streak sıfır (kalkanla kurtulsa bile
                # — kalkan sadece hayatta tutar, puan kazandırmaz).
                player.streak = 0
                round_score = 0

            player.round_scores.append(round_score)
            player.score += round_score

            player_answers[player.username] = {
                "answer": answer,
                "time_remaining": time_remaining,
                "correct": is_correct,
                "score": round_score,
                "total_score": player.score,
                "streak": player.streak,
            }

            if not is_correct:
                wrong_players.append(player.username)
            else:
                survivors.append(player.username)

        # Special rules from CLAUDE.md:
        # - If everyone would be eliminated, nobody is eliminated.
        #   Bu kural KALKANDAN ÖNCE uygulanır: kimse elenmeyecekse kimsenin
        #   kalkanı da boşa kırılmaz.
        if len(wrong_players) == len(self.alive_players):
            eliminated = []
            survivors = [p.username for p in self.alive_players]
        else:
            # KALKAN (🛡️): Tur 1-4'te yanlış cevaplayanın kalkanı varsa
            # elenmek yerine kalkan KIRILIR, oyuncu hayatta kalır (puansız).
            # Finalde (tahmin) bu yol zaten çalışmaz (_end_estimation_round).
            shields_active = self.current_round <= 4
            for username in wrong_players:
                player = self.players[username]
                if shields_active and player.shields > 0:
                    player.shields -= 1
                    shield_saved.append(username)
                    survivors.append(username)
                    # Reveal'da mobilin kişi bazında da okuyabilmesi için işaret.
                    player_answers[username]["shield_saved"] = True
                else:
                    eliminated.append(username)

        # - If nobody is eliminated, everyone continues
        # (this is the default behavior)

        # - Must have at least 2 players for final round
        if self.current_round == 4 and len(survivors) < 2:
            # Don't eliminate anyone this round
            eliminated = []
            survivors = [p.username for p in self.alive_players]

        # Apply eliminations
        for username in eliminated:
            player = self.players[username]
            player.is_alive = False
            player.eliminated_at_round = self.current_round

        # HAYALET cevaplar: elemeye/skora etkisiz, sadece sayaç + reveal bilgisi.
        ghost_results = self._resolve_ghost_answers(
            lambda ans: ans == correct_answer
        )

        result = RoundResult(
            round_number=self.current_round,
            question=question,
            correct_answer=correct_answer,
            player_answers=player_answers,
            eliminated=eliminated,
            survivors=survivors,
            shield_saved=shield_saved,
            ghost_results=ghost_results,
        )
        self.round_results.append(result)
        self.status = "round_end"

        return result

    def _end_estimation_round(self, correct_answer: float, question: dict) -> RoundResult:
        """Handle the final estimation round.

        ADİL ELEME (BUG FIX): Eskiden SADECE en yakın 1 oyuncu hayatta kalır,
        DİĞER HERKES — doğru cevabı TAM tutturmuş olsa bile — elenirdi. Bu,
        oyuncunun "doğru bildim ama elendim/yanlış sayıldım" şikayetine yol
        açıyordu (özellikle turnuvada zor tahmin sorularında belirgin, çünkü
        hard botlar real_answer'a çok yakın tahmin edip oyuncuyu tie-break ile
        eliyordu).

        Yeni kural: doğru cevaba TOLERANS bandı içinde yaklaşan HERKES hayatta
        kalır ve ``correct=True`` işaretlenir. Hiç kimse banda giremezse battle
        royale'in daralması için yalnızca en yakın oyuncu hayatta kalır (oyun
        kilitlenmesin). En yakın oyuncu ayrıca "winner" zafer bonusunu alır.
        """
        player_answers = {}
        real_answer = float(correct_answer)

        # Tolerans bandı: aralığın %10'u (yoksa |real|*%10, o da yoksa makul bir
        # taban). Bu bandın İÇİNDE kalan tahmin "doğru" sayılır → elenmez.
        min_val = question.get("min_value")
        max_val = question.get("max_value")
        if min_val is not None and max_val is not None and max_val > min_val:
            tolerance = 0.10 * (float(max_val) - float(min_val))
        else:
            tolerance = max(0.10 * abs(real_answer), 1.0)

        # Calculate distances
        distances: list[tuple[str, float, float]] = []  # (username, answer, distance)

        for player in self.alive_players:
            answer = player.current_answer
            if answer is None:
                # No answer = max distance
                answer = question.get("max_value", 1000)

            distance = abs(float(answer) - real_answer)
            distances.append((player.username, float(answer), distance))

            player.total_answers += 1

            player_answers[player.username] = {
                "answer": answer,
                "distance": distance,
                "time_remaining": player.answer_time or 0,
            }

        # Sort by distance (closest first), tie-break by time
        distances.sort(key=lambda x: (x[2], -(self.players[x[0]].answer_time or 0)))

        # Winner is the closest (zafer bonusu + en yüksek skor için).
        winner_username = distances[0][0] if distances else None

        # Tolerans içinde kalan herkes "doğru" → hayatta kalır. Kimse giremezse
        # en yakın oyuncuyu yine de kurtar (oyun ilerlesin).
        survivor_set = {u for u, _a, d in distances if d <= tolerance}
        if not survivor_set and winner_username is not None:
            survivor_set = {winner_username}

        eliminated = []
        survivors = []

        for username, answer, distance in distances:
            player = self.players[username]
            is_survivor = username in survivor_set
            if is_survivor:
                # Hayatta kalan: doğru tahmin → tur skoru. En yakın oyuncu ayrıca
                # streak +1 ile zafer bonusu kazanır.
                is_winner = username == winner_username
                round_score = calculate_round_score(
                    time_remaining_seconds=player.answer_time or 0,
                    is_correct=True,
                    streak_count=player.streak + 1,
                )
                player.streak += 1
                player.round_scores.append(round_score)
                player.score += round_score
                player.correct_answers += 1
                survivors.append(username)
                player_answers[username]["winner"] = is_winner
                player_answers[username]["correct"] = True
                player_answers[username]["score"] = round_score
            else:
                player.streak = 0
                player.round_scores.append(0)
                eliminated.append(username)
                player.is_alive = False
                player.eliminated_at_round = 5
                player_answers[username]["winner"] = False
                player_answers[username]["correct"] = False
                player_answers[username]["score"] = 0

        # HAYALET cevaplar: tahmin turunda tolerans bandı içi "doğru" sayılır.
        ghost_results = self._resolve_ghost_answers(
            lambda ans: ans is not None
            and abs(float(ans) - real_answer) <= tolerance
        )

        result = RoundResult(
            round_number=5,
            question=question,
            correct_answer=correct_answer,
            player_answers=player_answers,
            eliminated=eliminated,
            survivors=survivors,
            ghost_results=ghost_results,
        )
        self.round_results.append(result)
        return result

    def _estimation_round_winner(self) -> str | None:
        """Son OYNANAN tur bir TAHMİN turuysa, o turun kazananını döndür.

        Tahmin turu "en iyi performans gösteren (real_answer'a en yakın) kazanır"
        kuralıyla işler. ``_end_estimation_round`` real_answer'a en yakın oyuncuyu
        ``player_answers[username]["winner"] = True`` ile işaretler. Oyun bu tura
        kadar geldiyse, NİHAİ kazanan da bu olmalıdır — biriken skor değil.

        Returns:
            Tahmin turunun kazanan kullanıcı adı; son tur tahmin değilse None.
        """
        if not self.round_results:
            return None
        last = self.round_results[-1]
        if (last.question or {}).get("type") != "tahmin":
            return None
        for username, ans in last.player_answers.items():
            if ans.get("winner"):
                return username
        return None

    def _determine_winner_username(self) -> str | None:
        """Resolve the battle-royale winner.

        Priority:
        0. If the game reached the final ESTIMATION round, the winner is whoever
           was closest to the real answer that round (best performance wins) —
           NOT whoever accumulated the most score across rounds. Without this,
           the tolerance-band fix lets several players (often bots) survive the
           final round, and the highest *accumulated* score (frequently a bot)
           would steal the win from a player who nailed the estimate. This is
           the root cause of "I answered correctly but still lost / got
           eliminated" in tournament matches.
        1. If exactly one player is still alive, that player wins (last one
           standing) regardless of which round the game stopped at — covers
           the case where everyone else was eliminated early.
        2. If several players are still alive (no-elimination edge case that is
           NOT the estimation round), the alive player with the highest
           accumulated score wins.
        3. If nobody is alive (everyone eliminated the same round), fall back to
           the player who survived the longest, tie-broken by score, so the
           game always reports a winner.
        """
        # 0. Estimation round decides the winner by closeness, not total score.
        estimation_winner = self._estimation_round_winner()
        if estimation_winner is not None:
            return estimation_winner

        alive = self.alive_players
        if len(alive) == 1:
            return alive[0].username
        if len(alive) > 1:
            best = max(alive, key=lambda p: p.score)
            return best.username
        # Nobody alive — pick furthest survivor, then highest score.
        if not self.players:
            return None
        best = max(
            self.players.values(),
            key=lambda p: ((p.eliminated_at_round or 0), p.score),
        )
        return best.username

    def finish_game(self) -> dict:
        """Finalize the game and determine winner."""
        self.status = "finished"
        self.ended_at = datetime.now(timezone.utc)

        winner_username = self._determine_winner_username()

        # Calculate final scores
        results = []
        for player in self.players.values():
            rounds_survived = player.eliminated_at_round or 5
            is_winner = player.username == winner_username

            final_score = calculate_game_score(
                rounds_survived=rounds_survived,
                round_scores=player.round_scores,
                is_winner=is_winner,
            )
            player.score = final_score

            if is_winner:
                self.winner = player

            results.append({
                "username": player.username,
                "display_name": player.display_name,
                "avatar_id": player.avatar_id,
                "is_bot": player.is_bot,
                "frame": player.frame,
                "name_color": player.name_color,
                "effect": player.effect,
                "score": final_score,
                "rounds_survived": rounds_survived,
                "correct_answers": player.correct_answers,
                "total_answers": player.total_answers,
                "is_winner": is_winner,
                "eliminated_at_round": player.eliminated_at_round,
            })

        # Sort by score descending
        results.sort(key=lambda r: r["score"], reverse=True)

        return {
            "type": "game_over",
            "game_id": self.game_id,
            "winner": {
                "username": self.winner.username if self.winner else None,
                "display_name": self.winner.display_name if self.winner else None,
                "score": self.winner.score if self.winner else 0,
            },
            "leaderboard": results,
            "total_rounds": self.current_round,
            "duration_seconds": int((self.ended_at - self.started_at).total_seconds()),
        }

    def players_summary(self) -> list[dict]:
        """Return the per-player snapshot used by every broadcast.

        The is_alive / score fields here are the single source of truth the
        mobile client uses to compute "how many players are left".
        """
        return [
            {
                "username": p.username,
                "display_name": p.display_name,
                "avatar_id": p.avatar_id,
                "is_alive": p.is_alive,
                "score": p.score,
                "is_bot": p.is_bot,
                # Kalan kalkan sayısı (mobil 🛡️ rozetini bundan çizer).
                "shields": p.shields,
                "frame": p.frame,
                "name_color": p.name_color,
                "effect": p.effect,
            }
            for p in self.players.values()
        ]

    def get_round_end_message(self, result: RoundResult) -> dict:
        """Build the round-end message for clients."""
        # Contract-shaped results map: {username: {correct: bool, score: int}}
        results_map: dict[str, dict] = {}
        for username, ans in result.player_answers.items():
            results_map[username] = {
                "correct": ans.get("correct", ans.get("winner", False)),
                "score": ans.get("score", 0),
                "answer": ans.get("answer"),
                # Kalkanıyla kurtuldu mu? (top-level shield_saved listesinin
                # kişi bazlı karşılığı — mobil hangisini isterse onu okur)
                "shield_saved": bool(ans.get("shield_saved", False)),
                "total_score": ans.get("total_score", self.players[username].score
                                       if username in self.players else 0),
            }

        players = self.players_summary()
        return {
            "type": "round_end",
            "game_id": self.game_id,
            "round": result.round_number,
            "correct_answer": result.correct_answer,
            # New contract key:
            "results": results_map,
            # Backward-compatible key:
            "player_results": result.player_answers,
            "eliminated": result.eliminated,
            "eliminated_count": len(result.eliminated),
            # Bu tur kalkanıyla kurtulan (yanlış cevapladı ama elenmedi)
            # oyuncuların username listesi. Finalde her zaman boştur.
            "shield_saved": result.shield_saved,
            # HAYALET (👻) sonuçlar: {username: {answer, correct}} — elenmiş
            # oyuncuların gölge cevapları. Mobil yalnızca KENDİ girdisini okur;
            # results map'ine karışmaz, skor/eleme etkilemez.
            "ghost_results": result.ghost_results,
            "survivors": result.survivors,
            "survivors_count": len(result.survivors),
            "alive_count": self.alive_count,
            "players": players,
            "allPlayers": players,
        }


# --- Active Games Registry ---

active_games: dict[str, GameEngine] = {}


def create_game(
    game_id: str,
    players: list[dict],
    bots: list[dict],
    is_tournament: bool = False,
) -> GameEngine:
    """Create and register a new game."""
    engine = GameEngine(game_id, players, bots, is_tournament=is_tournament)
    active_games[game_id] = engine
    return engine


def get_game(game_id: str) -> GameEngine | None:
    """Get an active game by ID."""
    return active_games.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a finished game."""
    active_games.pop(game_id, None)
