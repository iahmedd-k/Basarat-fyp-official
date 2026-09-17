"""replace datetime.utcnow with func.now() and add timezone

Revision ID: a1b2c3d4e5f6
Revises: 6347e6f196a0
Create Date: 2026-09-17 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '6347e6f196a0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- users table ---
    op.alter_column(
        'users', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )
    op.alter_column(
        'users', 'updated_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )

    # --- refresh_tokens table ---
    op.alter_column(
        'refresh_tokens', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )

    # --- password_reset_tokens table ---
    op.alter_column(
        'password_reset_tokens', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )

    # --- devices table ---
    op.alter_column(
        'devices', 'created_at',
        existing_type=sa.DateTime(),
        type_=sa.DateTime(timezone=True),
        server_default=sa.func.now(),
    )


def downgrade() -> None:
    op.alter_column(
        'devices', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        server_default=None,
    )
    op.alter_column(
        'password_reset_tokens', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        server_default=None,
    )
    op.alter_column(
        'refresh_tokens', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        server_default=None,
    )
    op.alter_column(
        'users', 'updated_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        server_default=None,
    )
    op.alter_column(
        'users', 'created_at',
        existing_type=sa.DateTime(timezone=True),
        type_=sa.DateTime(),
        server_default=None,
    )
