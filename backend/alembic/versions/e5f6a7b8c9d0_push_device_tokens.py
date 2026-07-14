"""push_device_tokens — FCM cihaz token'ları tablosu (device_tokens)

Push bildirim altyapısı:
  - device_tokens.user_id: FK users.id (ON DELETE CASCADE), indeksli. Bir
    kullanıcının birden fazla cihazı olabilir → TEKİL DEĞİL.
  - device_tokens.token: FCM registration token. KÜRESEL TEKİL — aynı token
    iki kullanıcıya bağlanamaz (cihaz el değiştirirse token yeni kullanıcıya
    taşınır).
  - device_tokens.platform: "ios" | "android".
  - created_at / updated_at: token tazeliği (ölü cihaz ayıklama) için.

Yalnızca YENİ tablo eklenir; mevcut tablolara DOKUNULMAZ → Railway'de
`alembic upgrade head` kesintisiz çalışır, geri alınabilir (downgrade tabloyu
düşürür).

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-07-14 10:00:00.000000
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'device_tokens',
        sa.Column('id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('token', sa.String(length=255), nullable=False),
        sa.Column('platform', sa.String(length=10), nullable=False,
                  server_default='ios'),
        sa.Column('created_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True),
                  server_default=sa.text('now()'), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_device_tokens_user_id', 'device_tokens', ['user_id'])
    # Token küresel TEKİL (unique index): aynı cihaz iki kez kaydolamaz.
    op.create_index('ix_device_tokens_token', 'device_tokens', ['token'], unique=True)


def downgrade() -> None:
    op.drop_index('ix_device_tokens_token', table_name='device_tokens')
    op.drop_index('ix_device_tokens_user_id', table_name='device_tokens')
    op.drop_table('device_tokens')
