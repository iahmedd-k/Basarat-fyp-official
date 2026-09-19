"""rebuild community module (drop legacy tables, create new schema)

Revision ID: c3d4e5f6a8b9
Revises: b2c3d4e5f6a7
Create Date: 2026-09-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a8b9'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Drop the legacy community tables (children first) ─────────────────────
    # The old module used posts/comments/votes/reports with an incompatible
    # schema (votes, singular symbol tag, stance-only content). Rebuild clean.
    for table in ('votes', 'comments', 'reports', 'posts'):
        op.execute(f"DROP TABLE IF EXISTS {table} CASCADE")

    # ── posts ─────────────────────────────────────────────────────────────────
    op.create_table(
        'posts',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('content', sa.String(length=500), nullable=False),
        sa.Column('sentiment', sa.String(length=10), nullable=True),
        sa.Column('media_url', sa.Text(), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='PUBLISHED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("sentiment IN ('BULLISH','BEARISH','NEUTRAL')", name='ck_posts_sentiment'),
        sa.CheckConstraint("status IN ('PUBLISHED','REMOVED','FLAGGED')", name='ck_posts_status'),
        sa.CheckConstraint('length(content) BETWEEN 1 AND 500', name='ck_posts_content_len'),
    )
    op.create_index(op.f('ix_posts_user_id'), 'posts', ['user_id'])

    # ── post_stock_tags (1-3 real tickers per post) ──────────────────────────
    op.create_table(
        'post_stock_tags',
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('symbol', sa.String(length=10), sa.ForeignKey('stocks.symbol'), primary_key=True),
    )
    op.create_index('idx_post_stock_tags_symbol', 'post_stock_tags', ['symbol'])

    # ── post_likes (toggle, unique (post_id, user_id)) ────────────────────────
    op.create_table(
        'post_likes',
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), primary_key=True),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), primary_key=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )

    # ── comments (max depth 2) ────────────────────────────────────────────────
    op.create_table(
        'comments',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('parent_comment_id', sa.String(length=36), sa.ForeignKey('comments.id'), nullable=True),
        sa.Column('content', sa.String(length=300), nullable=False),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='PUBLISHED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.CheckConstraint("status IN ('PUBLISHED','REMOVED')", name='ck_comments_status'),
        sa.CheckConstraint('length(content) BETWEEN 1 AND 300', name='ck_comments_content_len'),
    )
    op.create_index('idx_comments_post_id', 'comments', ['post_id'])

    # ── reports (posts or comments, one per reporter per target) ──────────────
    op.create_table(
        'reports',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('reporter_user_id', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('target_type', sa.String(length=10), nullable=False),
        sa.Column('target_id', sa.String(length=36), nullable=False),
        sa.Column('reason', sa.String(length=50), nullable=False),
        sa.Column('status', sa.String(length=12), nullable=False, server_default='PENDING'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
        sa.UniqueConstraint('reporter_user_id', 'target_type', 'target_id', name='uq_reports_reporter_target'),
        sa.CheckConstraint("target_type IN ('POST','COMMENT')", name='ck_reports_target_type'),
        sa.CheckConstraint("status IN ('PENDING','REVIEWED','DISMISSED')", name='ck_reports_status'),
        sa.CheckConstraint(
            "reason IN ('SPAM','MISLEADING_INFO','HARASSMENT','OFF_TOPIC','OTHER')",
            name='ck_reports_reason',
        ),
    )
    op.create_index('idx_reports_target', 'reports', ['target_type', 'target_id'])

    # ── share_links ───────────────────────────────────────────────────────────
    op.create_table(
        'share_links',
        sa.Column('short_code', sa.String(length=12), primary_key=True),
        sa.Column('post_id', sa.String(length=36), sa.ForeignKey('posts.id', ondelete='CASCADE'), nullable=False),
        sa.Column('created_by', sa.String(length=36), sa.ForeignKey('users.id'), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.text('now()')),
    )


def downgrade() -> None:
    op.drop_table('share_links')
    op.drop_table('reports')
    op.drop_index('idx_comments_post_id', table_name='comments')
    op.drop_table('comments')
    op.drop_table('post_likes')
    op.drop_index('idx_post_stock_tags_symbol', table_name='post_stock_tags')
    op.drop_table('post_stock_tags')
    op.drop_index(op.f('ix_posts_user_id'), table_name='posts')
    op.drop_table('posts')