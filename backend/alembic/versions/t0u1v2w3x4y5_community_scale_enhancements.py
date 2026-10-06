"""community scale enhancements

Revision ID: t0u1v2w3x4y5
Revises: s9t0u1v2w3x4
Create Date: 2026-10-05 23:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 't0u1v2w3x4y5'
down_revision: Union[str, None] = 's9t0u1v2w3x4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    # 1. Add new columns to community_posts
    if 'community_posts' in existing_tables:
        existing_cols = {c['name'] for c in inspector.get_columns('community_posts')}
        if 'media_metadata' not in existing_cols:
            op.add_column('community_posts', sa.Column('media_metadata', sa.Text(), nullable=True))
        if 'price_at_post' not in existing_cols:
            op.add_column('community_posts', sa.Column('price_at_post', sa.Float(), nullable=True))
        if 'view_count' not in existing_cols:
            op.add_column('community_posts', sa.Column('view_count', sa.Integer(), nullable=False, server_default='0'))
        if 'bookmark_count' not in existing_cols:
            op.add_column('community_posts', sa.Column('bookmark_count', sa.Integer(), nullable=False, server_default='0'))
        if 'is_edited' not in existing_cols:
            op.add_column('community_posts', sa.Column('is_edited', sa.Boolean(), nullable=False, server_default='false'))
        if 'edited_at' not in existing_cols:
            op.add_column('community_posts', sa.Column('edited_at', sa.DateTime(timezone=True), nullable=True))

        existing_indexes = {i['name'] for i in inspector.get_indexes('community_posts')}
        if 'ix_community_posts_author_status_created' not in existing_indexes:
            op.create_index('ix_community_posts_author_status_created', 'community_posts', ['author_id', 'status', 'created_at'])
        if 'ix_community_posts_status_created_id' not in existing_indexes:
            op.create_index('ix_community_posts_status_created_id', 'community_posts', ['status', 'created_at', 'id'])

    # 2. Add reply_count to community_comments
    if 'community_comments' in existing_tables:
        existing_comment_cols = {c['name'] for c in inspector.get_columns('community_comments')}
        if 'reply_count' not in existing_comment_cols:
            op.add_column('community_comments', sa.Column('reply_count', sa.Integer(), nullable=False, server_default='0'))
        existing_comment_indexes = {i['name'] for i in inspector.get_indexes('community_comments')}
        if 'ix_community_comments_post_parent_created' not in existing_comment_indexes:
            op.create_index('ix_community_comments_post_parent_created', 'community_comments', ['post_id', 'parent_comment_id', 'created_at', 'id'])

    # 3. Create community_post_tickers table
    if 'community_post_tickers' not in existing_tables:
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

    # 4. Create community_bookmarks table
    if 'community_bookmarks' not in existing_tables:
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

    # 5. Create community_idempotency_keys table
    if 'community_idempotency_keys' not in existing_tables:
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

    # 6. Additional composite indexes
    if 'community_notifications' in existing_tables:
        existing_notif_indexes = {i['name'] for i in inspector.get_indexes('community_notifications')}
        if 'ix_community_notifications_recipient_unread_created' not in existing_notif_indexes:
            op.create_index('ix_community_notifications_recipient_unread_created', 'community_notifications', ['recipient_id', 'is_read', 'created_at'])

    if 'community_post_likes' in existing_tables:
        existing_like_indexes = {i['name'] for i in inspector.get_indexes('community_post_likes')}
        if 'ix_community_post_likes_user_created' not in existing_like_indexes:
            op.create_index('ix_community_post_likes_user_created', 'community_post_likes', ['user_id', 'created_at'])


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    existing_tables = set(inspector.get_table_names())

    if 'community_post_likes' in existing_tables:
        existing_like_indexes = {i['name'] for i in inspector.get_indexes('community_post_likes')}
        if 'ix_community_post_likes_user_created' in existing_like_indexes:
            op.drop_index('ix_community_post_likes_user_created', 'community_post_likes')

    if 'community_notifications' in existing_tables:
        existing_notif_indexes = {i['name'] for i in inspector.get_indexes('community_notifications')}
        if 'ix_community_notifications_recipient_unread_created' in existing_notif_indexes:
            op.drop_index('ix_community_notifications_recipient_unread_created', 'community_notifications')

    if 'community_idempotency_keys' in existing_tables:
        op.drop_table('community_idempotency_keys')

    if 'community_bookmarks' in existing_tables:
        op.drop_table('community_bookmarks')

    if 'community_post_tickers' in existing_tables:
        op.drop_table('community_post_tickers')

    if 'community_comments' in existing_tables:
        existing_comment_indexes = {i['name'] for i in inspector.get_indexes('community_comments')}
        if 'ix_community_comments_post_parent_created' in existing_comment_indexes:
            op.drop_index('ix_community_comments_post_parent_created', 'community_comments')
        existing_comment_cols = {c['name'] for c in inspector.get_columns('community_comments')}
        if 'reply_count' in existing_comment_cols:
            op.drop_column('community_comments', 'reply_count')

    if 'community_posts' in existing_tables:
        existing_post_indexes = {i['name'] for i in inspector.get_indexes('community_posts')}
        if 'ix_community_posts_status_created_id' in existing_post_indexes:
            op.drop_index('ix_community_posts_status_created_id', 'community_posts')
        if 'ix_community_posts_author_status_created' in existing_post_indexes:
            op.drop_index('ix_community_posts_author_status_created', 'community_posts')
        existing_cols = {c['name'] for c in inspector.get_columns('community_posts')}
        if 'edited_at' in existing_cols:
            op.drop_column('community_posts', 'edited_at')
        if 'is_edited' in existing_cols:
            op.drop_column('community_posts', 'is_edited')
        if 'bookmark_count' in existing_cols:
            op.drop_column('community_posts', 'bookmark_count')
        if 'view_count' in existing_cols:
            op.drop_column('community_posts', 'view_count')
        if 'price_at_post' in existing_cols:
            op.drop_column('community_posts', 'price_at_post')
        if 'media_metadata' in existing_cols:
            op.drop_column('community_posts', 'media_metadata')
