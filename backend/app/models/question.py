"""Question and QuestionHistory models — trivia question bank."""

import enum
import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.types import JSON
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class QuestionType(str, enum.Enum):
    """Question format types matching game round types."""
    DOGRU_YANLIS = "dogru_yanlis"
    GORSEL = "gorsel"
    KARSILASTIRMA = "karsilastirma"
    COKTAN_SECMELI = "coktan_secmeli"
    TAHMIN = "tahmin"


class ApprovalStatus(str, enum.Enum):
    """Question review pipeline states."""
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    SUSPENDED = "suspended"


class Question(Base):
    """A trivia question in the question bank.

    Follows the JSON schema defined in CLAUDE.md Section 3.1.
    Supports all question types: true/false, visual, comparison,
    multiple choice, and slider estimation.
    """

    __tablename__ = "questions"

    id: Mapped[str] = mapped_column(
        String(20), primary_key=True  # e.g. "q_00142"
    )
    type: Mapped[QuestionType] = mapped_column(
        Enum(QuestionType, name="question_type"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    difficulty: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    round_suitability: Mapped[list[int] | None] = mapped_column(
        JSON, nullable=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    options: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    correct_answer: Mapped[int | None] = mapped_column(Integer, nullable=True)
    time_seconds: Mapped[int] = mapped_column(Integer, default=7)
    explanation: Mapped[str | None] = mapped_column(Text, nullable=True)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    source: Mapped[str | None] = mapped_column(String(50), nullable=True)
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus, name="approval_status"),
        default=ApprovalStatus.PENDING,
        index=True,
    )
    usage_count: Mapped[int] = mapped_column(Integer, default=0)
    correct_rate: Mapped[float | None] = mapped_column(Float, nullable=True)
    report_count: Mapped[int] = mapped_column(Integer, default=0)

    # Estimation (tahmin) question fields
    min_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value: Mapped[float | None] = mapped_column(Float, nullable=True)
    real_answer: Mapped[float | None] = mapped_column(Float, nullable=True)
    scale: Mapped[str | None] = mapped_column(String(20), nullable=True)
    unit: Mapped[str | None] = mapped_column(String(20), nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )

    def __repr__(self) -> str:
        return f"<Question(id={self.id}, type={self.type}, category={self.category})>"


class QuestionHistory(Base):
    """Tracks which questions a user has seen and their answers.

    Used for:
    - 30-day dedup (same question not shown within 30 days)
    - Correct rate calculation
    - Difficulty balancing
    """

    __tablename__ = "question_history"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    question_id: Mapped[str] = mapped_column(
        String(20), ForeignKey("questions.id"), nullable=False, index=True
    )
    game_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("games.id", ondelete="CASCADE"), nullable=False
    )
    shown_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now()
    )
    was_correct: Mapped[bool] = mapped_column(Boolean, nullable=False)
    answer_time_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    def __repr__(self) -> str:
        return f"<QuestionHistory(user={self.user_id}, question={self.question_id}, correct={self.was_correct})>"
