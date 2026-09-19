"""add community module tables

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-09-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, None] = 'b2c3d4e5f6a7'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # community_posts
    op.create_table(
        'community_posts',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('author_id', sa.String(36), nullable=False),
        sa.Column('post_type', sa.String(20), nullable=False),
        sa.Column('stock_symbol', sa.String(20), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('image_url', sa.String(500), nullable=True),
        sa.Column('image_public_id', sa.String(255), nullable=True),
        sa.Column('like_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('comment_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('report_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('status', sa.String(30), nullable=False, server_default='PUBLISHED'),
        sa.Column('removed_reason', sa.String(30), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['stock_symbol'], ['stocks.symbol']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_posts_author_created', 'community_posts', ['author_id', 'created_at'])
    op.create_index('ix_community_posts_stock_created', 'community_posts', ['stock_symbol', 'created_at'])
    op.create_index('ix_community_posts_status_created', 'community_posts', ['status', 'created_at'])
    op.create_index('ix_community_posts_type_created', 'community_posts', ['post_type', 'created_at'])
    op.create_index('ix_community_posts_created_id', 'community_posts', ['created_at', 'id'])
    op.create_check_constraint(
        'ck_community_posts_type_stock_consistency',
        'community_posts',
        "(post_type = 'STOCK' AND stock_symbol IS NOT NULL) OR (post_type = 'GENERAL_MARKET' AND stock_symbol IS NULL)"
    )
    op.create_check_constraint(
        'ck_community_posts_status',
        'community_posts',
        "status IN ('PUBLISHED', 'TEMPORARILY_HIDDEN', 'DELETED')"
    )
    op.create_check_constraint(
        'ck_community_posts_removed_reason',
        'community_posts',
        "removed_reason IS NULL OR removed_reason IN ('USER_DELETED', 'MODERATION')"
    )
    op.create_check_constraint(
        'ck_community_posts_post_type',
        'community_posts',
        "post_type IN ('STOCK', 'GENERAL_MARKET')"
    )

    # community_post_likes
    op.create_table(
        'community_post_likes',
        sa.Column('post_id', sa.String(36), nullable=False),
        sa.Column('user_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('post_id', 'user_id'),
    )
    op.create_unique_constraint('uq_community_post_likes_post_user', 'community_post_likes', ['post_id', 'user_id'])

    # community_comments
    op.create_table(
        'community_comments',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('post_id', sa.String(36), nullable=False),
        sa.Column('author_id', sa.String(36), nullable=False),
        sa.Column('parent_comment_id', sa.String(36), nullable=True),
        sa.Column('content', sa.Text(), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PUBLISHED'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['author_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['parent_comment_id'], ['community_comments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_comments_post_created', 'community_comments', ['post_id', 'created_at'])
    op.create_index('ix_community_comments_author_created', 'community_comments', ['author_id', 'created_at'])
    op.create_check_constraint(
        'ck_community_comments_status',
        'community_comments',
        "status IN ('PUBLISHED', 'DELETED')"
    )

    # community_follows
    op.create_table(
        'community_follows',
        sa.Column('follower_id', sa.String(36), nullable=False),
        sa.Column('following_id', sa.String(36), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['follower_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['following_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('follower_id', 'following_id'),
    )
    op.create_unique_constraint('uq_community_follows_follower_following', 'community_follows', ['follower_id', 'following_id'])
    op.create_check_constraint(
        'ck_community_follows_no_self_follow',
        'community_follows',
        'follower_id != following_id'
    )
    op.create_index('ix_community_follows_follower_created', 'community_follows', ['follower_id', 'created_at'])
    op.create_index('ix_community_follows_following_created', 'community_follows', ['following_id', 'created_at'])

    # community_reports
    op.create_table(
        'community_reports',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('reporter_id', sa.String(36), nullable=False),
        sa.Column('post_id', sa.String(36), nullable=True),
        sa.Column('comment_id', sa.String(36), nullable=True),
        sa.Column('reason', sa.String(20), nullable=False),
        sa.Column('status', sa.String(20), nullable=False, server_default='PENDING'),
        sa.Column('reviewed_by', sa.String(36), nullable=True),
        sa.Column('reviewed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['reporter_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['comment_id'], ['community_comments.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['reviewed_by'], ['users.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_reports_status_created', 'community_reports', ['status', 'created_at'])
    op.create_index('ix_community_reports_post_status', 'community_reports', ['post_id', 'status'])
    op.create_index('ix_community_reports_comment_status', 'community_reports', ['comment_id', 'status'])
    op.create_check_constraint(
        'ck_community_reports_single_target',
        'community_reports',
        '(post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL)'
    )
    op.create_check_constraint(
        'ck_community_reports_reason',
        'community_reports',
        "reason IN ('SPAM', 'OFF_TOPIC', 'MISLEADING', 'ABUSIVE', 'OTHER')"
    )
    op.create_check_constraint(
        'ck_community_reports_status',
        'community_reports',
        "status IN ('PENDING', 'DISMISSED', 'REVIEWED')"
    )
    # Unique partial indexes for duplicate prevention
    op.execute("CREATE UNIQUE INDEX uq_community_reports_reporter_post ON community_reports (reporter_id, post_id) WHERE post_id IS NOT NULL")
    op.execute("CREATE UNIQUE INDEX uq_community_reports_reporter_comment ON community_reports (reporter_id, comment_id) WHERE comment_id IS NOT NULL")

    # community_moderation_actions
    op.create_table(
        'community_moderation_actions',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('moderator_id', sa.String(36), nullable=True),
        sa.Column('post_id', sa.String(36), nullable=True),
        sa.Column('comment_id', sa.String(36), nullable=True),
        sa.Column('action', sa.String(30), nullable=False),
        sa.Column('note', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['moderator_id'], ['users.id']),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['comment_id'], ['community_comments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_moderation_actions_post_created', 'community_moderation_actions', ['post_id', 'created_at'])
    op.create_index('ix_community_moderation_actions_comment_created', 'community_moderation_actions', ['comment_id', 'created_at'])
    op.create_index('ix_community_moderation_actions_moderator_created', 'community_moderation_actions', ['moderator_id', 'created_at'])
    op.create_check_constraint(
        'ck_community_moderation_actions_action',
        'community_moderation_actions',
        "action IN ('AUTO_HIDDEN', 'RESTORED', 'POST_DELETED', 'COMMENT_DELETED', 'DIRECT_REMOVAL')"
    )
    op.create_check_constraint(
        'ck_community_moderation_actions_single_target',
        'community_moderation_actions',
        '(post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL)'
    )

    # community_notifications
    op.create_table(
        'community_notifications',
        sa.Column('id', sa.String(36), nullable=False),
        sa.Column('recipient_id', sa.String(36), nullable=False),
        sa.Column('actor_id', sa.String(36), nullable=True),
        sa.Column('post_id', sa.String(36), nullable=True),
        sa.Column('comment_id', sa.String(36), nullable=True),
        sa.Column('type', sa.String(40), nullable=False),
        sa.Column('title', sa.String(255), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('is_read', sa.Boolean(), nullable=False, server_default='false'),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(['recipient_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['actor_id'], ['users.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['post_id'], ['community_posts.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['comment_id'], ['community_comments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_community_notifications_recipient_created', 'community_notifications', ['recipient_id', 'created_at'])
    op.create_index('ix_community_notifications_recipient_unread', 'community_notifications', ['recipient_id', 'is_read'])
    op.create_check_constraint(
        'ck_community_notifications_type',
        'community_notifications',
        "type IN ('POST_LIKED', 'POST_COMMENTED', 'COMMENT_REPLIED', 'USER_FOLLOWED', 'POST_AUTO_HIDDEN', 'POST_RESTORED', 'POST_MODERATION_DELETED')"
    )


def downgrade() -> None:
    op.drop_table('community_notifications')
    op.drop_table('community_moderation_actions')
    op.drop_table('community_reports')
    op.drop_table('community_follows')
    op.drop_table('community_comments')
    op.drop_table('community_post_likes')
    op.drop_table('community_posts')