"""Question-related Pydantic schemas."""

from datetime import datetime

from pydantic import BaseModel


class QuestionResponse(BaseModel):
    """Question sent to players during a game (no answer!)."""
    id: str
    type: str
    category: str
    content: str
    options: dict | None
    time_seconds: int
    image_url: str | None
    # Estimation fields (tahmin)
    min_value: float | None
    max_value: float | None
    scale: str | None
    unit: str | None

    model_config = {"from_attributes": True}


class QuestionAdminResponse(QuestionResponse):
    """Full question for admin/review (includes answer)."""
    difficulty: int
    correct_answer: int | None
    real_answer: float | None
    explanation: str | None
    source: str | None
    approval_status: str
    usage_count: int
    correct_rate: float | None
    report_count: int
    created_at: datetime

    model_config = {"from_attributes": True}
