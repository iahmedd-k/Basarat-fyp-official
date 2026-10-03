"""add persisted stock fundamentals snapshots

Revision ID: s9t0u1v2w3x4
Revises: r8s9t0u1v2w3
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "s9t0u1v2w3x4"
down_revision: Union[str, None] = "r8s9t0u1v2w3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "stock_fundamentals",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("stock_id", sa.String(36), sa.ForeignKey("stocks.id", ondelete="SET NULL")),
        sa.Column("symbol", sa.String(20), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("data_status", sa.String(30), nullable=False, server_default="complete"),
        sa.Column("source_as_of_date", sa.String(30)),
        sa.Column("fetched_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_successful_at", sa.DateTime(timezone=True)),
        sa.Column("refresh_run_id", sa.String(36)),
        sa.Column("payload_version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("last_error", sa.Text()),
        sa.UniqueConstraint("symbol", name="uq_stock_fundamentals_symbol"),
    )
    op.create_index("ix_stock_fundamentals_stock_id", "stock_fundamentals", ["stock_id"])
    op.create_index("ix_stock_fundamentals_symbol", "stock_fundamentals", ["symbol"])
    op.create_index("ix_stock_fundamentals_refresh_run_id", "stock_fundamentals", ["refresh_run_id"])

    op.create_table(
        "fundamentals_refresh_runs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True)),
        sa.Column("expected_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("success_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("partial_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("status", sa.String(30), nullable=False, server_default="running"),
        sa.Column("error", sa.Text()),
    )


def downgrade() -> None:
    op.drop_table("fundamentals_refresh_runs")
    op.drop_index("ix_stock_fundamentals_refresh_run_id", table_name="stock_fundamentals")
    op.drop_index("ix_stock_fundamentals_symbol", table_name="stock_fundamentals")
    op.drop_index("ix_stock_fundamentals_stock_id", table_name="stock_fundamentals")
    op.drop_table("stock_fundamentals")
