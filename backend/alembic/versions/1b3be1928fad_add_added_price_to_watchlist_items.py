"""add added_price to watchlist_items

Revision ID: 1b3be1928fad
Revises: n5o6p7q8r9s0
Create Date: 2026-09-30 02:00:04.443340

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1b3be1928fad'
down_revision: Union[str, None] = 'n5o6p7q8r9s0'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('watchlist_items', sa.Column('added_price', sa.Numeric(precision=18, scale=4), nullable=True))


def downgrade() -> None:
    op.drop_column('watchlist_items', 'added_price')
