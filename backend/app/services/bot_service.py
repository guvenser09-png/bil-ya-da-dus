"""Bot service — AI-controlled opponents for lobby filling.

Bot behavior from CLAUDE.md Section 2.2:
- 3 difficulty levels: Easy (50% correct), Medium (70%), Hard (85%)
- As rounds progress, harder bots remain (realism)
- Answer times randomly distributed 1-7 seconds
- Realistic Turkish names from a pool of 500 variants
- No "bot" label in UI — players should not notice
- Bot info logged server-side

TODO (Week 4): Full implementation with:
- Bot name generator (500+ realistic Turkish names)
- Difficulty-based answer simulation
- Realistic answer timing
- Bot elimination logic (harder bots survive longer)
"""

import random

# Sample Turkish bot names (expand to 500+ in Week 4)
BOT_NAMES = [
    "ahmet_42", "deniz.k", "elifg", "mertcan99", "zeynep_s",
    "burak.ylmz", "selin123", "emre_tr", "ayse.d", "can_85",
    "defne.oz", "oguz_k", "melis33", "baris.y", "ece_dev",
    "kaan_07", "irem.g", "umut_42", "naz.b", "onur_99",
    "cemre.t", "arda_21", "pinar.k", "yusuf.m", "tugce_s",
    "serkan.b", "gizem_77", "hakan.d", "sibel.y", "kerem_01",
    "damla.c", "erdem_55", "ilknur.p", "volkan.a", "betul_34",
    "alp.k", "gamze.r", "tuna_88", "seda.m", "berke_16",
    "duygu.e", "koray_73", "ipek.s", "tolga.b", "elif_22",
    "caner.y", "aslı_05", "doruk.t", "merve.k", "utku_61",
]


def generate_bot_name() -> str:
    """Generate a random realistic bot username."""
    return random.choice(BOT_NAMES)


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


def generate_bot_answer_time() -> float:
    """Generate a realistic answer time for a bot (1-7 seconds)."""
    return round(random.uniform(1.0, 7.0), 1)
