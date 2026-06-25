"""add_question_quality_fields

Revision ID: a1b2c3d4e5f6
Revises: 3fc9f5948121
Create Date: 2026-05-15 12:00:00.000000

Adds user_rating_sum, user_rating_count, and is_daily_challenge columns to
the questions table to support the question quality and daily-challenge systems.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: Union[str, None] = "3fc9f5948121"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add quality-control and daily-challenge columns to the questions table."""
    op.add_column(
        "questions",
        sa.Column(
            "user_rating_sum",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "questions",
        sa.Column(
            "user_rating_count",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )
    op.add_column(
        "questions",
        sa.Column(
            "is_daily_challenge",
            sa.Boolean(),
            nullable=False,
            server_default="false",
        ),
    )


def downgrade() -> None:
    """Remove quality-control and daily-challenge columns from questions table."""
    op.drop_column("questions", "is_daily_challenge")
    op.drop_column("questions", "user_rating_count")
    op.drop_column("questions", "user_rating_sum")
