"""tournament_ranked_season — aylık ranked sezon puanı + settlement tabloları

Turnuva modu + aylık sıralama sezonu (first-Monday) için iki yeni tablo:
  - season_scores: (user_id, season_id) başına ranked sezon puanı (her ay sıfırlanır).
  - season_settlements: sezon sonu ödül dağıtımı idempotency işareti.

Battle Pass (User.season_points) ve mevcut leaderboard akışı DEĞİŞMEDİ.

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-13 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'season_scores',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('season_id', sa.String(length=7), nullable=False),
        sa.Column('points', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('user_id', 'season_id', name='uq_season_scores_user_season'),
    )
    op.create_index('ix_season_scores_user_id', 'season_scores', ['user_id'])
    op.create_index('ix_season_scores_season_id', 'season_scores', ['season_id'])

    op.create_table(
        'season_settlements',
        sa.Column('season_id', sa.String(length=7), nullable=False),
        sa.Column('settled_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=True),
        sa.Column('rewarded_count', sa.Integer(), nullable=False, server_default='0'),
        sa.PrimaryKeyConstraint('season_id'),
    )


def downgrade() -> None:
    op.drop_table('season_settlements')
    op.drop_index('ix_season_scores_season_id', table_name='season_scores')
    op.drop_index('ix_season_scores_user_id', table_name='season_scores')
    op.drop_table('season_scores')
