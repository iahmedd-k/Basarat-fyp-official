"""Add durable company and daily-analysis stock data."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p9q0r1s2t3u4"
down_revision: Union[str, Sequence[str], None] = ("h8i9j0k1l2m3", "o6p7q8r9s0t1")
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Remove accidental duplicate daily bars before enforcing idempotent upserts.
    op.execute("""
        DELETE FROM stock_prices old
        USING stock_prices newer
        WHERE old.stock_id = newer.stock_id AND old.date = newer.date
          AND old.ctid < newer.ctid
    """)
    op.create_unique_constraint(
        "uq_stock_prices_stock_date", "stock_prices", ["stock_id", "date"]
    )
    op.create_table(
        "stock_reference_data",
        sa.Column("stock_id", sa.String(length=36), nullable=False),
        sa.Column("profile_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("fundamentals_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("dividends_json", sa.JSON(), server_default="[]", nullable=False),
        sa.Column("fundamentals_response_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("profile_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("fundamentals_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("dividends_fetched_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("stock_id"),
    )
    op.create_table(
        "stock_daily_analysis",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("stock_id", sa.String(length=36), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("technical_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("risk_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("recommendation_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["stock_id"], ["stocks.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("stock_id", "as_of_date", name="uq_stock_daily_analysis_stock_date"),
    )
    op.create_index("ix_stock_daily_analysis_stock_id", "stock_daily_analysis", ["stock_id"])
    op.create_index("ix_stock_daily_analysis_as_of_date", "stock_daily_analysis", ["as_of_date"])


def downgrade() -> None:
    op.drop_index("ix_stock_daily_analysis_as_of_date", table_name="stock_daily_analysis")
    op.drop_index("ix_stock_daily_analysis_stock_id", table_name="stock_daily_analysis")
    op.drop_table("stock_daily_analysis")
    op.drop_table("stock_reference_data")
    op.drop_constraint("uq_stock_prices_stock_date", "stock_prices", type_="unique")
