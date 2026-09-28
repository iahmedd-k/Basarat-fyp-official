"""add ipos and etfs tables

Revision ID: m4n5o6p7q8r9
Revises: l3m4n5o6p7q8
Create Date: 2026-09-28
"""

from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa


revision: str = "m4n5o6p7q8r9"
down_revision: Union[str, Sequence[str], None] = "l3m4n5o6p7q8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. IPOS table
    op.create_table(
        "ipos",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), unique=True, nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("sector", sa.String(100), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="UPCOMING"),
        sa.Column("issue_size_shares", sa.Float(), nullable=True),
        sa.Column("issue_size_pkr", sa.Float(), nullable=True),
        sa.Column("floor_price", sa.Float(), nullable=True),
        sa.Column("strike_price", sa.Float(), nullable=True),
        sa.Column("listing_price", sa.Float(), nullable=True),
        sa.Column("current_price", sa.Float(), nullable=True),
        sa.Column("book_building_start", sa.Date(), nullable=True),
        sa.Column("book_building_end", sa.Date(), nullable=True),
        sa.Column("public_subscription_start", sa.Date(), nullable=True),
        sa.Column("public_subscription_end", sa.Date(), nullable=True),
        sa.Column("listing_date", sa.Date(), nullable=True),
        sa.Column("lead_manager", sa.String(255), nullable=True),
        sa.Column("is_shariah_compliant", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("prospectus_url", sa.String(500), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("subscription_multiplier", sa.Float(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_ipos_symbol", "ipos", ["symbol"])
    op.create_index("ix_ipos_status", "ipos", ["status"])
    op.create_index("ix_ipos_sector", "ipos", ["sector"])
    op.create_index("ix_ipos_listing_date", "ipos", ["listing_date"])
    op.create_index("ix_ipos_status_listing_date", "ipos", ["status", "listing_date"])

    # 2. ETFS table
    op.create_table(
        "etfs",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("symbol", sa.String(20), unique=True, nullable=False),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("fund_manager", sa.String(255), nullable=False),
        sa.Column("category", sa.String(100), nullable=False),
        sa.Column("benchmark_index", sa.String(255), nullable=False),
        sa.Column("is_shariah_compliant", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("expense_ratio", sa.Float(), nullable=True),
        sa.Column("inception_date", sa.Date(), nullable=True),
        sa.Column("total_assets_pkr", sa.Float(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_etfs_symbol", "etfs", ["symbol"])
    op.create_index("ix_etfs_category", "etfs", ["category"])
    op.create_index("ix_etfs_is_shariah_compliant", "etfs", ["is_shariah_compliant"])
    op.create_index("ix_etfs_is_active", "etfs", ["is_active"])
    op.create_index("ix_etfs_shariah_active", "etfs", ["is_shariah_compliant", "is_active"])


def downgrade() -> None:
    op.drop_index("ix_etfs_shariah_active", table_name="etfs")
    op.drop_index("ix_etfs_is_active", table_name="etfs")
    op.drop_index("ix_etfs_is_shariah_compliant", table_name="etfs")
    op.drop_index("ix_etfs_category", table_name="etfs")
    op.drop_index("ix_etfs_symbol", table_name="etfs")
    op.drop_table("etfs")

    op.drop_index("ix_ipos_status_listing_date", table_name="ipos")
    op.drop_index("ix_ipos_listing_date", table_name="ipos")
    op.drop_index("ix_ipos_sector", table_name="ipos")
    op.drop_index("ix_ipos_status", table_name="ipos")
    op.drop_index("ix_ipos_symbol", table_name="ipos")
    op.drop_table("ipos")
