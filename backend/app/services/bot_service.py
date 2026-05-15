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
from itertools import product

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

# Pre-generate 500+ names
_ALL_BOT_NAMES: list[str] = []


def _generate_name_pool() -> list[str]:
    """Generate a pool of 500+ realistic Turkish usernames."""
    names = set()

    for first in _FIRST_NAMES:
        for last in _LAST_PARTS:
            for sep in _SEPARATORS:
                name = f"{first}{sep}{last}"
                if 5 <= len(name) <= 15:
                    names.add(name)
                if len(names) >= 600:
                    break
            if len(names) >= 600:
                break

    # Add some extra patterns
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


def generate_bot_answer_time(difficulty: str = "medium") -> float:
    """Generate a realistic answer time for a bot (1-7 seconds).

    Harder bots tend to answer slightly faster.
    """
    speed_ranges = {
        "easy": (2.5, 6.5),
        "medium": (1.5, 5.0),
        "hard": (0.8, 3.5),
    }
    min_time, max_time = speed_ranges.get(difficulty, (1.5, 5.0))
    return round(random.uniform(min_time, max_time), 1)


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
