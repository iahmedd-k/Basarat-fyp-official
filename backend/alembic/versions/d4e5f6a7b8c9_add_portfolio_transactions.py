"""add portfolio transactions table

Revision ID: d4e5f6a7b8c9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # portfolio_transactions
    op.create_table(
        'portfolio_transactions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('transaction_type', sa.String(10), nullable=False),
        sa.Column('quantity', sa.Numeric(18, 4), nullable=False),
        sa.Column('price', sa.Numeric(18, 4), nullable=False),
        sa.Column('fee', sa.Numeric(18, 4), nullable=False, server_default='0'),
        sa.Column('transaction_date', sa.Date(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol'], ['stocks.symbol'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_portfolio_transactions_user_symbol', 'portfolio_transactions', ['user_id', 'symbol'])
    op.create_index('ix_portfolio_transactions_user_date', 'portfolio_transactions', ['user_id', 'transaction_date'])
    op.create_check_constraint(
        'ck_portfolio_transactions_type',
        'portfolio_transactions',
        "transaction_type IN ('BUY', 'SELL')"
    )
    op.create_check_constraint(
        'ck_portfolio_transactions_quantity_positive',
        'portfolio_transactions',
        'quantity > 0'
    )
    op.create_check_constraint(
        'ck_portfolio_transactions_price_nonnegative',
        'portfolio_transactions',
        'price >= 0'
    )
    op.create_check_constraint(
        'ck_portfolio_transactions_fee_nonnegative',
        'portfolio_transactions',
        'fee >= 0'
    )


def downgrade() -> None:
    op.drop_table('portfolio_transactions')