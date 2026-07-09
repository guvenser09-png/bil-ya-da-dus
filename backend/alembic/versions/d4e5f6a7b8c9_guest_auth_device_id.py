"""guest_auth_device_id — misafir girişi için device_id + is_guest kolonları

Misafir (guest) hesap akışı:
  - users.device_id: cihaz kimliği (nullable, unique, indexli). Mobil tarafta
    üretilip kalıcı saklanır; aynı cihaz tekrar girince aynı hesabı bulur.
  - users.is_guest: hesap misafir mi? Claim (kalıcılaştırma) ile False olur.

Mevcut satırlar etkilenmez: device_id NULL kalır, is_guest server_default ile
false yazılır (Railway'de alembic upgrade head kesintisiz çalışır).

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-07-09 12:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'users',
        sa.Column('device_id', sa.String(length=64), nullable=True),
    )
    op.add_column(
        'users',
        sa.Column('is_guest', sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # unique + index tek adımda (unique index).
    op.create_index('ix_users_device_id', 'users', ['device_id'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_users_device_id', table_name='users')
    op.drop_column('users', 'is_guest')
    op.drop_column('users', 'device_id')
