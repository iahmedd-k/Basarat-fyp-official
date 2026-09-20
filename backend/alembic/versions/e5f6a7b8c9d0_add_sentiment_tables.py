"""add sentiment result and aggregate tables

Revision ID: e5f6a7b8c9d0
Revises: d4e5f6a7b8c9
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'e5f6a7b8c9d0'
down_revision: Union[str, None] = 'd4e5f6a7b8c9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # sentiment_results
    op.create_table(
        'sentiment_results',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('news_article_id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('model_name', sa.String(50), nullable=False),
        sa.Column('label', sa.String(20), nullable=False),
        sa.Column('score', sa.Numeric(4, 3), nullable=False),
        sa.Column('positive_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('neutral_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('negative_score', sa.Numeric(4, 3), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['news_article_id'], ['news_articles.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['symbol'], ['stocks.symbol']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_sentiment_results_symbol_created', 'sentiment_results', ['symbol', 'created_at'])
    op.create_index('ix_sentiment_results_news_symbol', 'sentiment_results', ['news_article_id', 'symbol'])

    # sentiment_aggregates
    op.create_table(
        'sentiment_aggregates',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('symbol', sa.String(20), nullable=False),
        sa.Column('period', sa.String(10), nullable=False),
        sa.Column('period_start', sa.DateTime(), nullable=False),
        sa.Column('period_end', sa.DateTime(), nullable=False),
        sa.Column('overall_score', sa.Numeric(4, 3), nullable=False),
        sa.Column('label', sa.String(20), nullable=False),
        sa.Column('article_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('positive_ratio', sa.Numeric(4, 3), nullable=True),
        sa.Column('neutral_ratio', sa.Numeric(4, 3), nullable=True),
        sa.Column('negative_ratio', sa.Numeric(4, 3), nullable=True),
        sa.Column('trend', sa.String(20), nullable=True),
        sa.Column('daily_scores', sa.Text(), nullable=True),
        sa.Column('source_breakdown', sa.Text(), nullable=True),
        sa.Column('computed_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['symbol'], ['stocks.symbol']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_unique_constraint('uq_sentiment_agg_symbol_period', 'sentiment_aggregates', ['symbol', 'period', 'period_end'])
    op.create_index('ix_sentiment_aggregates_symbol_period', 'sentiment_aggregates', ['symbol', 'period'])


def downgrade() -> None:
    op.drop_table('sentiment_aggregates')
    op.drop_table('sentiment_results')