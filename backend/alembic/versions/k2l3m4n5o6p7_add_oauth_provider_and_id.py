"""add oauth_provider and oauth_id to users

Revision ID: k2l3m4n5o6p7
Revises: j1k2l3m4n5o6
Create Date: 2026-09-26
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k2l3m4n5o6p7"
down_revision: Union[str, Sequence[str], None] = "j1k2l3m4n5o6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("oauth_provider", sa.String(50), nullable=True))
    op.add_column("users", sa.Column("oauth_id", sa.String(255), nullable=True))
    op.create_index("ix_users_oauth_id", "users", ["oauth_id"])


def downgrade() -> None:
    op.drop_index("ix_users_oauth_id", table_name="users")
    op.drop_column("users", "oauth_id")
    op.drop_column("users", "oauth_provider")
