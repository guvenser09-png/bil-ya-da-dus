"""Game-related Pydantic schemas."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class GameParticipantResponse(BaseModel):
    """A participant in a game."""
    user_id: uuid.UUID | None
    bot_name: str | None
    is_bot: bool
    score: int
    final_round: int
    eliminated_at_round: int | None

    model_config = {"from_attributes": True}


class GameResponse(BaseModel):
    """Game summary response."""
    id: uuid.UUID
    started_at: datetime
    ended_at: datetime | None
    winner_id: uuid.UUID | None
    player_count: int
    bot_count: int
    status: str
    current_round: int
    participants: list[GameParticipantResponse] = []

    model_config = {"from_attributes": True}


class GameHistoryResponse(BaseModel):
    """Paginated game history."""
    games: list[GameResponse]
    total: int
    page: int
    page_size: int
