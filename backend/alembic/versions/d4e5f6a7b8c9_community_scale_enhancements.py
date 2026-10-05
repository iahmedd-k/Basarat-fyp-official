"""community scale enhancements

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-10-05 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4e5f6a7b8c9'
down_revision: Union[str, None] = 'c3d4e5f6a7b8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Add new columns to community_posts
    op.add_column('community_posts', sa.Column('media_metadata', sa.Text(), nullable=True))
    op.add_column('community_posts', sa.Column('price_at_post', sa.Float(), nullable=True))
    op.add_column('community_posts', sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('community_posts', sa.Column('bookmark_count', sa.Integer(), nullable=False, server_default='0'))
    op.add_column('community_posts', sa.Column('is_edited', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('community_posts', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))

    # 2. Add composite indexes on community_posts
    op.create_index('ix_community_posts_author_status_created', 'community_posts', ['author_id', 'status', 'created_at'])
    op.create_index('ix_community_posts_status_created_id', 'community_posts', ['status', 'created_at', 'id'])

    # 3. Add reply_count to community_comments
    op.add_column('community_comments', sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'))
    op.create_index('ix_community_comments_post_parent_created', 'community_comments', ['post_id', 'parent_comment_id', 'created_at', 'id'])

    # 4. Create community_post_tickers table
    op.create_table(
        'community_post_tickers',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('post_id', sa.String(36), nullable=False),
        sa.Column('ticker', sa.String(20), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_unique_constraint('uq_community_post_tickers_post_ticker', 'community_post_tickers', ['post_id', 'ticker'])
    op.create_index('ix_community_post_tickers_ticker_created', 'community_post_tickers', ['ticker', 'created_at'])
    op.create_index('ix_community_post_tickers_ticker_id', 'community_post_tickers', ['ticker', 'post_id'])

    # 5. Create community_bookmarks table
    op.create_table(
        'community_bookmarks',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('post_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_unique_constraint('uq_community_bookmarks_post_user', 'community_bookmarks', ['post_id', 'user_id'])
    op.create_index('ix_community_bookmarks_user_created', 'community_bookmarks', ['user_id', 'created_at'])

    # 6. Create community_idempotency_keys table
    op.create_table(
        'community_idempotency_keys',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('key', sa.String(128), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('endpoint', sa.String(100), nullable=False),
        sa.Column('response_code', sa.Integer(), nullable=True),
        sa.Column('response_body', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_unique_constraint('uq_community_idempotency_user_key', 'community_idempotency_keys', ['user_id', 'key'])
    op.create_index('ix_community_idempotency_expires', 'community_idempotency_keys', ['expires_at'])

    # 7. Additional composite index on notifications
    op.create_index('ix_community_notifications_recipient_unread_created', 'community_notifications', ['recipient_id', 'is_read', 'created_at'])
    op.create_index('ix_community_post_likes_user_created', 'community_post_likes', ['user_id', 'created_at'])


def downgrade() -> None:
    op.drop_index('ix_community_post_likes_user_created', 'community_post_likes')
    op.drop_index('ix_community_notifications_recipient_unread_created', 'community_notifications')
    op.drop_table('community_idempotency_keys')
    op.drop_table('community_bookmarks')
    op.drop_table('community_post_tickers')
    op.drop_index('ix_community_comments_post_parent_created', 'community_comments')
    op.drop_column('community_comments', 'reply_count')
    op.drop_index('ix_community_posts_status_created_id', 'community_posts')
    op.drop_index('ix_community_posts_author_status_created', 'community_posts')
    op.drop_column('community_posts', 'edited_at')
    op.drop_column('community_posts', 'is_edited')
    op.drop_column('community_posts', 'bookmark_count')
    op.drop_column('community_posts', 'view_count')
    op.drop_column('community_posts', 'price_at_post')
    op.drop_column('community_posts', 'media_metadata')
