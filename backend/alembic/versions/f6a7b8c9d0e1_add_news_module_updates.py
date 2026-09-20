"""add news module updates - source_key, external_id, link table, sentiment fields, indexes

Revision ID: f6a7b8c9d0e1
Revises: c3d4e5f6a7b8
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'f6a7b8c9d0e1'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── news_articles: add new columns ──────────────────────────────────────
    op.add_column('news_articles', sa.Column('source_key', sa.String(50), nullable=True, index=True))
    op.add_column('news_articles', sa.Column('source_type', sa.String(20), nullable=True))  # official | news
    op.add_column('news_articles', sa.Column('external_id', sa.String(100), nullable=True))
    op.add_column('news_articles', sa.Column('external_url', sa.Text(), nullable=True))
    op.add_column('news_articles', sa.Column('event_type', sa.String(50), nullable=True, index=True))
    op.add_column('news_articles', sa.Column('sentiment_label', sa.String(20), nullable=True))  # bullish|bearish|neutral
    op.add_column('news_articles', sa.Column('sentiment_score', sa.Numeric(4, 3), nullable=True))
    op.add_column('news_articles', sa.Column('sentiment_method', sa.String(20), nullable=True))  # finbert|eps_rule|none
    op.add_column('news_articles', sa.Column('sentiment_status', sa.String(20), nullable=True))  # ok|failed|skipped
    op.add_column('news_articles', sa.Column('published_at_estimated', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('news_articles', sa.Column('impact_score', sa.Integer(), nullable=True))
    op.add_column('news_articles', sa.Column('published_at', sa.DateTime(timezone=True), nullable=True, index=True))
    op.add_column('news_articles', sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()))
    op.add_column('news_articles', sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True, onupdate=sa.func.now()))

    # ── news_articles: add UNIQUE constraints ───────────────────────────────
    # UNIQUE on content_hash
    op.create_unique_constraint('uq_news_articles_content_hash', 'news_articles', ['content_hash'])
    # UNIQUE on (source_key, external_id) where external_id is not null
    op.execute("""
        CREATE UNIQUE INDEX uq_news_articles_source_key_external_id
        ON news_articles (source_key, external_id)
        WHERE external_id IS NOT NULL
    """)

    # ── news_articles: add composite indexes ────────────────────────────────
    op.create_index('ix_news_articles_published_at_id_desc', 'news_articles', [sa.text('published_at DESC'), sa.text('id DESC')])
    op.create_index('ix_news_articles_source_key_published_at_desc', 'news_articles', ['source_key', sa.text('published_at DESC')])

    # ── news_article_symbols link table ─────────────────────────────────────
    op.create_table(
        'news_article_symbols',
        sa.Column('article_id', sa.String(36), sa.ForeignKey('news_articles.id', ondelete='CASCADE'), primary_key=True, nullable=False),
        sa.Column('symbol', sa.String(20), primary_key=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index('ix_news_article_symbols_symbol_article_id', 'news_article_symbols', ['symbol', 'article_id'])

    # ── Backfill source_key and source_type from existing source column ─────
    # Map existing source names to keys
    op.execute("""
        UPDATE news_articles
        SET source_key = LOWER(REPLACE(source, ' ', '_')),
            source_type = CASE
                WHEN source IN ('PSX', 'SECP', 'SBP') THEN 'official'
                ELSE 'news'
            END
        WHERE source_key IS NULL
    """)

    # ── Per-source ingestion state table ────────────────────────────────────
    op.create_table(
        'news_source_state',
        sa.Column('source_key', sa.String(50), primary_key=True, nullable=False),
        sa.Column('last_run_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_success_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('last_error', sa.Text(), nullable=True),
        sa.Column('consecutive_failures', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_new_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('healthy', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # ── Symbol backfill state table ─────────────────────────────────────────
    op.create_table(
        'symbol_backfill_state',
        sa.Column('symbol', sa.String(20), primary_key=True, nullable=False),
        sa.Column('last_backfill_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('status', sa.String(20), nullable=False, server_default='pending'),  # pending|done|failed
        sa.Column('error', sa.Text(), nullable=True),
    )

    # ── Holiday/Override config table ───────────────────────────────────────
    op.create_table(
        'market_hours_config',
        sa.Column('id', sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column('name', sa.String(100), nullable=False, unique=True),
        sa.Column('config_json', sa.JSON(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='true'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
    )

    # Insert default market hours config
    op.execute("""
        INSERT INTO market_hours_config (name, config_json) VALUES
        ('default_weekly', '{
            "monday": {"open": "09:15", "close": "15:30"},
            "tuesday": {"open": "09:15", "close": "15:30"},
            "wednesday": {"open": "09:15", "close": "15:30"},
            "thursday": {"open": "09:15", "close": "15:30"},
            "friday": {"open": "09:00", "close": "16:30", "break": {"start": "12:00", "end": "14:30"}},
            "saturday": null,
            "sunday": null
        }'),
        ('holidays', '[]'),
        ('overrides', '[]')
        ON CONFLICT (name) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_table('market_hours_config')
    op.drop_table('symbol_backfill_state')
    op.drop_table('news_source_state')
    op.drop_table('news_article_symbols')
    op.drop_index('ix_news_articles_source_key_published_at_desc', table_name='news_articles')
    op.drop_index('ix_news_articles_published_at_id_desc', table_name='news_articles')
    op.execute("DROP INDEX IF EXISTS uq_news_articles_source_key_external_id")
    op.drop_constraint('uq_news_articles_content_hash', 'news_articles', type_='unique')
    op.drop_column('news_articles', 'updated_at')
    op.drop_column('news_articles', 'created_at')
    op.drop_column('news_articles', 'published_at')
    op.drop_column('news_articles', 'impact_score')
    op.drop_column('news_articles', 'published_at_estimated')
    op.drop_column('news_articles', 'sentiment_status')
    op.drop_column('news_articles', 'sentiment_method')
    op.drop_column('news_articles', 'sentiment_score')
    op.drop_column('news_articles', 'sentiment_label')
    op.drop_column('news_articles', 'event_type')
    op.drop_column('news_articles', 'external_url')
    op.drop_column('news_articles', 'external_id')
    op.drop_column('news_articles', 'source_type')
    op.drop_column('news_articles', 'source_key')