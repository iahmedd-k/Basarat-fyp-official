"""Enforce at most one default watchlist per user.

Revision ID: p6q7r8s9t0u1
Revises: n5o6p7q8r9s0
Create Date: 2026-10-01
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p6q7r8s9t0u1"
down_revision: Union[str, Sequence[str], None] = "n5o6p7q8r9s0"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(
        """
        UPDATE watchlists
        SET is_default = false
        WHERE is_default = true
          AND id NOT IN (
              SELECT id
              FROM (
                  SELECT id,
                         ROW_NUMBER() OVER (
                             PARTITION BY user_id
                             ORDER BY created_at ASC, id ASC
                         ) AS row_num
                  FROM watchlists
                  WHERE is_default = true
              ) ranked
              WHERE row_num = 1
          )
        """
    )
    op.create_index(
        "uq_watchlists_one_default_per_user",
        "watchlists",
        ["user_id"],
        unique=True,
        postgresql_where=sa.text("is_default = true"),
        sqlite_where=sa.text("is_default = 1"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_watchlists_one_default_per_user",
        table_name="watchlists",
    )