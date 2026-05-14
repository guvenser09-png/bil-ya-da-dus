"""Score calculation service.

Scoring rules from CLAUDE.md Section 4.1:
- Base Score       = Rounds survived × 10
- Speed Bonus      = (Remaining time × 2) per round
- Victory Bonus    = 100 (if player wins the game)
- Correct Bonus    = 5 per correct answer
- Streak Bonus     = Consecutive corrects: ×1.2, ×1.5, ×2 multiplier

TODO (Week 4): Full implementation with unit tests for 10+ scenarios.
"""


def calculate_round_score(
    time_remaining_seconds: float,
    is_correct: bool,
    streak_count: int,
) -> int:
    """Calculate score for a single round answer.

    Args:
        time_remaining_seconds: Time left when answer was submitted.
        is_correct: Whether the answer was correct.
        streak_count: Number of consecutive correct answers (0 if this is wrong).

    Returns:
        Score earned this round.
    """
    if not is_correct:
        return 0

    # Base correct bonus
    score = 5

    # Speed bonus
    speed_bonus = int(time_remaining_seconds * 2)
    score += speed_bonus

    # Streak multiplier
    if streak_count >= 3:
        score = int(score * 2.0)
    elif streak_count >= 2:
        score = int(score * 1.5)
    elif streak_count >= 1:
        score = int(score * 1.2)

    return score


def calculate_game_score(
    rounds_survived: int,
    round_scores: list[int],
    is_winner: bool,
) -> int:
    """Calculate total game score.

    Args:
        rounds_survived: Number of rounds the player survived (1-5).
        round_scores: List of scores earned each round.
        is_winner: Whether this player won the game.

    Returns:
        Total game score.
    """
    # Base score for survival
    total = rounds_survived * 10

    # Sum of round scores
    total += sum(round_scores)

    # Victory bonus
    if is_winner:
        total += 100

    return total
