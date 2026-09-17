"""initial schema

Revision ID: 6347e6f196a0
Revises: 
Create Date: 2026-09-16 20:08:28.262991

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '6347e6f196a0'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Drop legacy tables (messages first due to FK dependency on conversations)
    op.drop_table('messages')
    op.drop_table('conversations')

    # news_articles — new columns for the pipeline
    op.add_column('news_articles', sa.Column('source_type', sa.String(length=50), nullable=True))
    op.add_column('news_articles', sa.Column('content_hash', sa.String(length=64), nullable=True))
    op.add_column('news_articles', sa.Column('symbols', sa.Text(), nullable=True))
    op.add_column('news_articles', sa.Column('company_names', sa.Text(), nullable=True))
    op.add_column('news_articles', sa.Column('sector', sa.String(length=100), nullable=True))
    op.add_column('news_articles', sa.Column('event_type', sa.String(length=50), nullable=True))
    op.add_column('news_articles', sa.Column('sentiment_label', sa.String(length=20), nullable=True))
    op.add_column('news_articles', sa.Column('impact_score', sa.Integer(), nullable=True))
    op.add_column('news_articles', sa.Column('updated_at', sa.DateTime(), nullable=True))
    op.create_index('ix_news_articles_content_hash', 'news_articles', ['content_hash'], unique=True)
    op.create_index('ix_news_articles_event_type', 'news_articles', ['event_type'], unique=False)
    op.create_index('ix_news_articles_published_at', 'news_articles', ['published_at'], unique=False)
    op.create_index('ix_news_sentiment_label', 'news_articles', ['sentiment_label'], unique=False)
    op.create_index('ix_news_source', 'news_articles', ['source'], unique=False)

    # predictions — GRU + XGBoost model outputs
    op.add_column('predictions', sa.Column('gru_direction', sa.String(length=20), nullable=True))
    op.add_column('predictions', sa.Column('gru_bullish_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('gru_bearish_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('gru_sideways_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('gru_gap_pp', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('xgb_direction', sa.String(length=20), nullable=True))
    op.add_column('predictions', sa.Column('xgb_bullish_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('xgb_bearish_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('xgb_sideways_pct', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('xgb_gap_pp', sa.Float(), nullable=True))
    op.add_column('predictions', sa.Column('gate_reason', sa.String(length=100), nullable=True))

    # users — risk profile onboarding fields
    op.add_column('users', sa.Column('risk_tolerance', sa.String(length=20), nullable=True))
    op.add_column('users', sa.Column('sector_preferences', sa.JSON(), nullable=True))
    op.add_column('users', sa.Column('investment_horizon', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('users', 'investment_horizon')
    op.drop_column('users', 'sector_preferences')
    op.drop_column('users', 'risk_tolerance')
    op.drop_column('predictions', 'gate_reason')
    op.drop_column('predictions', 'xgb_gap_pp')
    op.drop_column('predictions', 'xgb_sideways_pct')
    op.drop_column('predictions', 'xgb_bearish_pct')
    op.drop_column('predictions', 'xgb_bullish_pct')
    op.drop_column('predictions', 'xgb_direction')
    op.drop_column('predictions', 'gru_gap_pp')
    op.drop_column('predictions', 'gru_sideways_pct')
    op.drop_column('predictions', 'gru_bearish_pct')
    op.drop_column('predictions', 'gru_bullish_pct')
    op.drop_column('predictions', 'gru_direction')
    op.drop_index('ix_news_source', table_name='news_articles')
    op.drop_index('ix_news_sentiment_label', table_name='news_articles')
    op.drop_index('ix_news_articles_published_at', table_name='news_articles')
    op.drop_index('ix_news_articles_event_type', table_name='news_articles')
    op.drop_index('ix_news_articles_content_hash', table_name='news_articles')
    op.drop_column('news_articles', 'updated_at')
    op.drop_column('news_articles', 'impact_score')
    op.drop_column('news_articles', 'sentiment_label')
    op.drop_column('news_articles', 'event_type')
    op.drop_column('news_articles', 'sector')
    op.drop_column('news_articles', 'company_names')
    op.drop_column('news_articles', 'symbols')
    op.drop_column('news_articles', 'content_hash')
    op.drop_column('news_articles', 'source_type')
