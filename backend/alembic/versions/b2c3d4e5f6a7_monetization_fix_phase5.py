"""monetization_fix_phase5 — maç ödülü cap, reklam ödülü cap, starter pack

Gelir modeli düzeltmesi (Phase 5): maç sonu coin ödülü günlük cap takibi,
ödüllü reklam günlük limit sayacı ve tek-seferlik starter pack bayrağı için
yeni User alanları.

Revision ID: b2c3d4e5f6a7
Revises: fa97faf7bee4
Create Date: 2026-06-11 20:30:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, None] = 'fa97faf7bee4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Maç ödülü günlük cap takibi.
    op.add_column('users', sa.Column('match_reward_date', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('match_reward_coins_today', sa.Integer(), nullable=False, server_default='0'))
    # Ödüllü reklam günlük limit sayacı.
    op.add_column('users', sa.Column('ad_reward_date', sa.String(length=10), nullable=True))
    op.add_column('users', sa.Column('ad_reward_count_today', sa.Integer(), nullable=False, server_default='0'))
    # Starter pack tek-seferlik satın alma bayrağı.
    op.add_column('users', sa.Column('starter_pack_purchased', sa.Boolean(), nullable=False, server_default=sa.false()))


def downgrade() -> None:
    op.drop_column('users', 'starter_pack_purchased')
    op.drop_column('users', 'ad_reward_count_today')
    op.drop_column('users', 'ad_reward_date')
    op.drop_column('users', 'match_reward_coins_today')
    op.drop_column('users', 'match_reward_date')
