"""add canonical stock references to watchlist items

Revision ID: r8s9t0u1v2w3
Revises: q7r8s9t0u1v2
Create Date: 2026-10-02
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r8s9t0u1v2w3"
down_revision: Union[str, Sequence[str], None] = "q7r8s9t0u1v2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch_op:
        batch_op.add_column(sa.Column("stock_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_watchlist_items_stock_id_stocks",
            "stocks",
            ["stock_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index("ix_watchlist_items_stock_id", ["stock_id"])
    op.execute(
        """
        UPDATE watchlist_items
        SET stock_id = (
            SELECT stocks.id
            FROM stocks
            WHERE UPPER(stocks.symbol) = UPPER(watchlist_items.symbol)
            LIMIT 1
        )
        WHERE EXISTS (
            SELECT 1
            FROM stocks
            WHERE UPPER(stocks.symbol) = UPPER(watchlist_items.symbol)
        )
        """
    )


def downgrade() -> None:
    with op.batch_alter_table("watchlist_items") as batch_op:
        batch_op.drop_index("ix_watchlist_items_stock_id")
        batch_op.drop_constraint(
            "fk_watchlist_items_stock_id_stocks",
            type_="foreignkey",
        )
        batch_op.drop_column("stock_id")
