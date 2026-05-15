"""Game engine — core game loop, round management, elimination logic.

Manages the entire game lifecycle from CLAUDE.md Section 1:
- 5 rounds with different question types
- Player elimination each round (wrong answers fall)
- Final round: slider estimation
- Score calculation and winner determination
- Bot behavior integration

Round structure:
| Round | Type              | Time | Difficulty | Elimination        |
|-------|-------------------|------|------------|-------------------|
| 1     | True/False        | 5s   | Very easy  | Wrong answers      |
| 2     | Visual            | 7s   | Easy       | Wrong answers      |
| 3     | Comparison        | 7s   | Medium     | Wrong answers      |
| 4     | Multiple choice   | 8s   | Med-hard   | Wrong answers      |
| 5     | Slider estimation | 8s   | Intuition  | Closest wins       |
"""

import asyncio
import random
import uuid as uuid_mod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from app.services.bot_service import (
    generate_bot_answer_time,
    should_bot_answer_correctly,
)
from app.services.score_service import calculate_game_score, calculate_round_score


# --- Round Configuration ---

ROUND_CONFIG = [
    {"round": 1, "type": "dogru_yanlis",    "time": 5, "difficulty": 1},
    {"round": 2, "type": "gorsel",          "time": 7, "difficulty": 2},
    {"round": 3, "type": "karsilastirma",   "time": 7, "difficulty": 3},
    {"round": 4, "type": "coktan_secmeli",  "time": 8, "difficulty": 4},
    {"round": 5, "type": "tahmin",          "time": 8, "difficulty": 5},
]


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
    is_alive: bool = True
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


class GameEngine:
    """Manages a single game's lifecycle."""

    def __init__(self, game_id: str, players: list[dict], bots: list[dict]):
        self.game_id = game_id
        self.status = "waiting"  # waiting, round_active, round_end, finished
        self.current_round = 0
        self.round_results: list[RoundResult] = []
        self.started_at = datetime.now(timezone.utc)
        self.ended_at: datetime | None = None
        self.winner: PlayerState | None = None

        # Initialize player states
        self.players: dict[str, PlayerState] = {}
        for p in players:
            uid = p.get("user_id", str(uuid_mod.uuid4()))
            self.players[p["username"]] = PlayerState(
                user_id=uid,
                username=p["username"],
                display_name=p.get("display_name", p["username"]),
                avatar_id=p.get("avatar_id", "default_01"),
                is_bot=False,
            )
        for b in bots:
            self.players[b["bot_name"]] = PlayerState(
                user_id=None,
                username=b["bot_name"],
                display_name=b["bot_name"],
                avatar_id=b.get("avatar_id", "default_01"),
                is_bot=True,
                bot_difficulty=b.get("difficulty", "medium"),
            )

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
        """Get configuration for the current round."""
        if 0 < self.current_round <= 5:
            return ROUND_CONFIG[self.current_round - 1]
        return ROUND_CONFIG[0]

    def start_round(self, question: dict) -> dict:
        """Start a new round. Returns round info for clients."""
        self.current_round += 1
        self.status = "round_active"

        config = self.get_round_config()

        # Reset answers for this round
        for p in self.alive_players:
            p.current_answer = None
            p.answer_time = None

        # Prepare question for clients (hide correct answer)
        client_question = {
            "id": question.get("id", f"q_{self.current_round}"),
            "type": config["type"],
            "content": question.get("content", ""),
            "options": question.get("options"),
            "image_url": question.get("image_url"),
            "time_seconds": config["time"],
        }

        # For estimation round, add slider config
        if config["type"] == "tahmin":
            client_question["min_value"] = question.get("min_value", 0)
            client_question["max_value"] = question.get("max_value", 1000)
            client_question["unit"] = question.get("unit", "")

        return {
            "type": "round_start",
            "round": self.current_round,
            "total_rounds": 5,
            "round_type": config["type"],
            "question": client_question,
            "alive_count": self.alive_count,
            "time_seconds": config["time"],
        }

    def submit_answer(self, username: str, answer: Any, time_remaining: float) -> bool:
        """Submit a player's answer. Returns True if accepted."""
        player = self.players.get(username)
        if not player or not player.is_alive or player.current_answer is not None:
            return False

        player.current_answer = answer
        player.answer_time = time_remaining
        return True

    def simulate_bot_answers(self, correct_answer: Any, question: dict) -> None:
        """Generate answers for all bots still alive."""
        config = self.get_round_config()

        for player in self.alive_players:
            if not player.is_bot or player.current_answer is not None:
                continue

            answer_time = generate_bot_answer_time()

            if config["type"] == "tahmin":
                # For estimation: generate a guess near the real answer
                real = question.get("real_answer", 500)
                min_val = question.get("min_value", 0)
                max_val = question.get("max_value", 1000)

                # Harder bots guess closer
                spread = {
                    "easy": 0.3,
                    "medium": 0.15,
                    "hard": 0.07,
                }.get(player.bot_difficulty, 0.15)

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
        config = self.get_round_config()
        eliminated = []
        survivors = []
        player_answers = {}

        if config["type"] == "tahmin":
            # Final round: closest to real answer wins
            return self._end_estimation_round(correct_answer, question)

        # Regular round: wrong answers are eliminated
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
                eliminated.append(player.username)
            else:
                survivors.append(player.username)

        # Special rules from CLAUDE.md:
        # - If everyone would be eliminated, nobody is eliminated
        if len(eliminated) == len(self.alive_players):
            eliminated = []
            survivors = [p.username for p in self.alive_players]

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

        result = RoundResult(
            round_number=self.current_round,
            question=question,
            correct_answer=correct_answer,
            player_answers=player_answers,
            eliminated=eliminated,
            survivors=survivors,
        )
        self.round_results.append(result)
        self.status = "round_end"

        return result

    def _end_estimation_round(self, correct_answer: float, question: dict) -> RoundResult:
        """Handle the final estimation round — closest answer wins."""
        player_answers = {}
        real_answer = float(correct_answer)

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

        # Winner is the closest
        winner_username = distances[0][0] if distances else None
        eliminated = []
        survivors = []

        for username, answer, distance in distances:
            player = self.players[username]
            if username == winner_username:
                # Winner gets victory bonus + round score
                round_score = calculate_round_score(
                    time_remaining_seconds=player.answer_time or 0,
                    is_correct=True,
                    streak_count=player.streak + 1,
                )
                player.round_scores.append(round_score)
                player.score += round_score
                player.correct_answers += 1
                survivors.append(username)
                player_answers[username]["winner"] = True
                player_answers[username]["score"] = round_score
            else:
                player.round_scores.append(0)
                eliminated.append(username)
                player.is_alive = False
                player.eliminated_at_round = 5
                player_answers[username]["winner"] = False
                player_answers[username]["score"] = 0

        result = RoundResult(
            round_number=5,
            question=question,
            correct_answer=correct_answer,
            player_answers=player_answers,
            eliminated=eliminated,
            survivors=survivors,
        )
        self.round_results.append(result)
        return result

    def finish_game(self) -> dict:
        """Finalize the game and determine winner."""
        self.status = "finished"
        self.ended_at = datetime.now(timezone.utc)

        # Calculate final scores
        results = []
        for player in self.players.values():
            rounds_survived = player.eliminated_at_round or 5
            is_winner = player.is_alive and self.current_round >= 5

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

    def get_round_end_message(self, result: RoundResult) -> dict:
        """Build the round-end message for clients."""
        return {
            "type": "round_end",
            "round": result.round_number,
            "correct_answer": result.correct_answer,
            "player_results": result.player_answers,
            "eliminated": result.eliminated,
            "eliminated_count": len(result.eliminated),
            "survivors": result.survivors,
            "survivors_count": len(result.survivors),
            "alive_count": self.alive_count,
        }


# --- Active Games Registry ---

active_games: dict[str, GameEngine] = {}


def create_game(game_id: str, players: list[dict], bots: list[dict]) -> GameEngine:
    """Create and register a new game."""
    engine = GameEngine(game_id, players, bots)
    active_games[game_id] = engine
    return engine


def get_game(game_id: str) -> GameEngine | None:
    """Get an active game by ID."""
    return active_games.get(game_id)


def remove_game(game_id: str) -> None:
    """Remove a finished game."""
    active_games.pop(game_id, None)
