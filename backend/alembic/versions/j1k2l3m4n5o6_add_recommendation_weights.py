"""persist per-user recommendation engine weights

Revision ID: j1k2l3m4n5o6
Revises: i1j2k3l4m5n6
Create Date: 2026-09-24
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j1k2l3m4n5o6"
down_revision: Union[str, Sequence[str], None] = "i1j2k3l4m5n6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("recommendation_weights", sa.JSON(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "recommendation_weights")
