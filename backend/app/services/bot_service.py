"""Bot service — AI-controlled opponents for lobby filling.

Bot behavior from CLAUDE.md Section 2.2:
- 3 difficulty levels: Easy (50% correct), Medium (70%), Hard (85%)
- As rounds progress, harder bots remain (realism)
- Answer times randomly distributed 1-7 seconds
- Realistic Turkish names from a pool of 500+ variants
- No "bot" label in UI — players should not notice
- Bot info logged server-side
"""

import random

# --- Turkish Name Components ---
_FIRST_NAMES = [
    "ahmet", "mehmet", "mustafa", "ali", "hasan", "hüseyin", "ibrahim", "ismail",
    "osman", "yusuf", "murat", "emre", "burak", "can", "deniz", "efe", "kaan",
    "kerem", "serkan", "volkan", "onur", "tuna", "arda", "berk", "koray",
    "umut", "doruk", "alp", "erdem", "caner", "berke", "tolga", "utku",
    "zeynep", "elif", "merve", "ayşe", "fatma", "emine", "selin", "irem",
    "ece", "defne", "damla", "pınar", "gizem", "gamze", "betül", "ilknur",
    "sibel", "seda", "duygu", "ipek", "aslı", "cemre", "naz", "tüğçe",
    "melis", "buse", "beril", "ezgi", "ceren", "su", "yağmur", "ada",
    "mert", "cem", "oğuz", "barış", "hakan", "turgut", "selim", "yiğit",
    "atlas", "rüzgar", "toprak", "demir", "çınar", "ayaz", "bora", "ege",
]

_LAST_PARTS = [
    "k", "y", "m", "s", "b", "d", "g", "t", "p", "c", "r", "n", "z",
    "oz", "tr", "ist", "dev", "pro", "gg", "42", "06", "34", "35", "61",
    "07", "16", "01", "55", "99", "77", "88", "21", "33", "44", "53",
    "ylmz", "kaya", "ozt", "snr", "gok", "yld", "dmr", "cln", "akr",
]

_SEPARATORS = [".", "_", ""]
_SUFFIXES = ["", "x", "q", "v", "123", "007", "tr", "gg", "pro"]

# Gerçekçi kullanıcı adı stillerini çeşitlendirmek için ek bileşenler.
# Hedef: "ayse_34", "mehmet61", "gamer_efe", "zeynep.k" gibi karışık stiller.
_NUM_TAILS = [
    "34", "06", "61", "35", "07", "16", "01", "55", "99", "77",
    "88", "21", "33", "53", "42", "27", "10", "23", "44", "67",
]
_GAMER_PREFIXES = ["gamer", "pro", "lord", "king", "mr", "the", "real", "xx"]
_INITIAL_SUFFIXES = ["k", "y", "d", "s", "g", "m", "c", "b", "t", "a"]

# Pre-generate 500+ names
_ALL_BOT_NAMES: list[str] = []


def _generate_name_pool() -> list[str]:
    """Generate a large pool of realistic, mixed-style Turkish usernames.

    Stiller karışık tutulur ki botlar gerçek oyuncudan ayırt edilemesin:
      - first+last       -> "mehmetkaya", "ayse.snr"
      - first+number     -> "mehmet61", "ayse34"
      - first_number     -> "ayse_34", "efe_07"
      - prefix_first     -> "gamer_efe", "proburak"
      - first.initial    -> "zeynep.k", "deniz.y"
      - first+suffix     -> "efepro", "canqq"
    """
    names = set()

    # 1) first + last (orijinal stil, ayraçlı/ayraçsız)
    for first in _FIRST_NAMES:
        for last in _LAST_PARTS:
            for sep in _SEPARATORS:
                name = f"{first}{sep}{last}"
                if 5 <= len(name) <= 15:
                    names.add(name)

    # 2) first + sayı (ayraçlı ve ayraçsız): "mehmet61", "ayse_34"
    for first in _FIRST_NAMES:
        for num in _NUM_TAILS:
            for sep in ("", "_", "."):
                name = f"{first}{sep}{num}"
                if 4 <= len(name) <= 15:
                    names.add(name)

    # 3) gamer/pro prefix + first: "gamer_efe", "proburak", "xx_deniz"
    for prefix in _GAMER_PREFIXES:
        for first in _FIRST_NAMES:
            for sep in ("_", ""):
                name = f"{prefix}{sep}{first}"
                if 5 <= len(name) <= 15:
                    names.add(name)

    # 4) first . baş harf: "zeynep.k", "deniz.y"
    for first in _FIRST_NAMES:
        for ini in _INITIAL_SUFFIXES:
            name = f"{first}.{ini}"
            if 4 <= len(name) <= 15:
                names.add(name)

    # 5) first + serbest suffix: "efepro", "canqq", "selin007"
    for first in _FIRST_NAMES:
        for suffix in _SUFFIXES:
            name = f"{first}{suffix}"
            if 4 <= len(name) <= 15:
                names.add(name)

    return list(names)


# Initialize on import
_ALL_BOT_NAMES = _generate_name_pool()


def generate_bot_name(exclude: set[str] | None = None) -> str:
    """Generate a random realistic bot username.

    Args:
        exclude: Set of names to avoid (existing players/bots).

    Returns:
        A unique bot username.
    """
    if not exclude:
        return random.choice(_ALL_BOT_NAMES)

    available = [n for n in _ALL_BOT_NAMES if n not in exclude]
    if not available:
        # Fallback: add random numbers
        base = random.choice(_ALL_BOT_NAMES)
        return f"{base}{random.randint(10, 99)}"

    return random.choice(available)


def should_bot_answer_correctly(difficulty: str, round_number: int) -> bool:
    """Determine if a bot answers correctly based on difficulty.

    Args:
        difficulty: 'easy', 'medium', or 'hard'
        round_number: Current round (1-5), harder rounds favor harder bots.

    Returns:
        True if bot answers correctly.
    """
    base_rates = {"easy": 0.50, "medium": 0.70, "hard": 0.85}
    rate = base_rates.get(difficulty, 0.60)

    # Slight adjustment per round (later rounds are harder)
    round_penalty = (round_number - 1) * 0.03
    adjusted_rate = max(rate - round_penalty, 0.20)

    return random.random() < adjusted_rate


def generate_bot_answer_time(
    difficulty: str = "medium",
    time_limit: float | None = None,
) -> float:
    """Bir bot için doğal dağılımlı cevap gecikmesi (saniye) üret.

    His için kritik: botlar sabit/aniden cevaplamasın. Gecikme, turun cevap
    penceresi içinde (yaklaşık 1.5 - (süre-1) sn) DOĞAL bir dağılımla seçilir;
    bazıları erken, bazıları son ana yakın cevaplar. Zorluk yalnızca eğilimi
    kaydırır (zor botlar biraz daha hızlı), adaleti DEĞİŞTİRMEZ — bu sadece
    görsel/his amaçlıdır, skor/eleme zamanlamadan etkilenmez.

    time_limit verilirse pencere ona göre ölçeklenir; verilmezse eski 1-7 sn
    davranışına yakın güvenli aralık kullanılır.
    """
    if time_limit is None:
        speed_ranges = {
            "easy": (2.5, 6.5),
            "medium": (1.5, 5.0),
            "hard": (0.8, 3.5),
        }
        min_time, max_time = speed_ranges.get(difficulty, (1.5, 5.0))
        return round(random.uniform(min_time, max_time), 1)

    # Pencere: en erken ~1.5sn, en geç ~ (süre - 1.0)sn.
    earliest = min(1.5, max(0.3, time_limit * 0.2))
    latest = max(earliest + 0.5, time_limit - 1.0)

    # Zorluğa göre eğilim: zor botlar pencerenin erken yarısına yatkın,
    # kolay botlar geç yarısına. Gauss ile doğal yayılım.
    center_frac = {"easy": 0.6, "medium": 0.5, "hard": 0.4}.get(difficulty, 0.5)
    center = earliest + (latest - earliest) * center_frac
    spread = (latest - earliest) * 0.30
    delay = random.gauss(center, spread)
    delay = max(earliest, min(latest, delay))
    return round(delay, 1)


# Tahmin (slider) turu sapma oranları: aralığın (max-min) yüzdesi olarak
# Gauss standart sapması. Zor botlar gerçek değere daha yakın tahmin eder.
_GUESS_SPREADS = {"easy": 0.30, "medium": 0.15, "hard": 0.07}
# İlk-maç senaryosu (cömert mod): sapma GENİŞLETİLİR ki yeni oyuncunun finali
# kazanma olasılığı belirgin artsın (easy %30 → %45 vb.).
_GENEROUS_GUESS_SPREADS = {"easy": 0.45, "medium": 0.25, "hard": 0.12}


def bot_guess_spread(difficulty: str, generous: bool = False) -> float:
    """Tahmin (slider) turunda botun sapma oranını döndür (aralığın yüzdesi).

    Args:
        difficulty: 'easy', 'medium' veya 'hard'.
        generous:   True ise ilk-maç senaryosu için genişletilmiş sapma
                    tablosu kullanılır (botlar daha kötü tahmin eder).

    Returns:
        Gauss standart sapması olarak kullanılacak oran (0-1 arası).
    """
    if generous:
        return _GENEROUS_GUESS_SPREADS.get(difficulty, 0.25)
    return _GUESS_SPREADS.get(difficulty, 0.15)


def should_bot_skip_answer(difficulty: str = "medium") -> bool:
    """Bot bu turda HİÇ cevap vermesin mi? (his için "süre doldu / cevapsız").

    Düşük olasılıkla botlar kararsız kalıp cevap vermez; bu, hep cevaplayan
    "robot" hissini kırar. Zor botlar daha nadir pas geçer. Yalnızca his
    amaçlıdır; pas geçen bot zaten yanlış/cevapsız sayılır, gerçek oyuncuya
    avantaj/dezavantaj yaratmaz.
    """
    skip_rates = {"easy": 0.10, "medium": 0.06, "hard": 0.03}
    return random.random() < skip_rates.get(difficulty, 0.06)


def get_bot_pool_count() -> int:
    """Return the number of available bot names."""
    return len(_ALL_BOT_NAMES)


def assign_bot_difficulties(bot_count: int) -> list[str]:
    """Assign difficulty levels to a group of bots.

    Distribution: ~30% easy, ~40% medium, ~30% hard
    """
    easy_count = max(1, int(bot_count * 0.3))
    hard_count = max(1, int(bot_count * 0.3))
    medium_count = bot_count - easy_count - hard_count

    difficulties = (
        ["easy"] * easy_count +
        ["medium"] * medium_count +
        ["hard"] * hard_count
    )
    random.shuffle(difficulties)
    return difficulties[:bot_count]
