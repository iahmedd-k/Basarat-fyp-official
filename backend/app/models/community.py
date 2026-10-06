from datetime import datetime, timezone
from enum import Enum as PyEnum
from typing import List, Optional

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.id_generator import generate_time_id
from app.db.base import Base


class PostType(PyEnum):
    STOCK = "STOCK"
    GENERAL_MARKET = "GENERAL_MARKET"


class PostStatus(PyEnum):
    PUBLISHED = "PUBLISHED"
    TEMPORARILY_HIDDEN = "TEMPORARILY_HIDDEN"
    DELETED = "DELETED"


class RemovedReason(PyEnum):
    USER_DELETED = "USER_DELETED"
    MODERATION = "MODERATION"


class ReportStatus(PyEnum):
    PENDING = "PENDING"
    DISMISSED = "DISMISSED"
    REVIEWED = "REVIEWED"


class ReportReason(PyEnum):
    SPAM = "SPAM"
    OFF_TOPIC = "OFF_TOPIC"
    MISLEADING = "MISLEADING"
    ABUSIVE = "ABUSIVE"
    OTHER = "OTHER"


class CommentStatus(PyEnum):
    PUBLISHED = "PUBLISHED"
    DELETED = "DELETED"


class ModerationActionType(PyEnum):
    AUTO_HIDDEN = "AUTO_HIDDEN"
    RESTORED = "RESTORED"
    POST_DELETED = "POST_DELETED"
    COMMENT_DELETED = "COMMENT_DELETED"
    DIRECT_REMOVAL = "DIRECT_REMOVAL"


class NotificationType(PyEnum):
    POST_LIKED = "POST_LIKED"
    POST_COMMENTED = "POST_COMMENTED"
    COMMENT_REPLIED = "COMMENT_REPLIED"
    USER_FOLLOWED = "USER_FOLLOWED"
    POST_AUTO_HIDDEN = "POST_AUTO_HIDDEN"
    POST_RESTORED = "POST_RESTORED"
    POST_MODERATION_DELETED = "POST_MODERATION_DELETED"


class CommunityPost(Base):
    __tablename__ = "community_posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_type: Mapped[str] = mapped_column(String(20), nullable=False)
    stock_symbol: Mapped[str | None] = mapped_column(String(20), ForeignKey("stocks.symbol"), nullable=True, index=True)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    image_url: Mapped[str | None] = mapped_column(String(500), nullable=True)
    image_public_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    media_metadata: Mapped[str | None] = mapped_column(Text, nullable=True)  # JSON: width, height, mime, etc.

    price_at_post: Mapped[float | None] = mapped_column(Float, nullable=True)

    like_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    report_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    view_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    bookmark_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    is_edited: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    edited_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    status: Mapped[str] = mapped_column(String(30), default=PostStatus.PUBLISHED.value, nullable=False)
    removed_reason: Mapped[str | None] = mapped_column(String(30), nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    author = relationship("User", back_populates="community_posts", lazy="selectin")
    stock = relationship("Stock", lazy="selectin")
    likes = relationship("CommunityPostLike", back_populates="post", lazy="select", cascade="all, delete-orphan")
    comments = relationship("CommunityComment", back_populates="post", lazy="select", cascade="all, delete-orphan")
    reports = relationship("CommunityReport", back_populates="post", lazy="select", cascade="all, delete-orphan")
    moderation_actions = relationship("CommunityModerationAction", back_populates="post", lazy="select", cascade="all, delete-orphan")
    tickers = relationship("CommunityPostTicker", back_populates="post", lazy="selectin", cascade="all, delete-orphan")
    bookmarks = relationship("CommunityBookmark", back_populates="post", lazy="select", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint(
            "(post_type = 'STOCK' AND stock_symbol IS NOT NULL) OR (post_type = 'GENERAL_MARKET' AND stock_symbol IS NULL)",
            name="ck_community_posts_type_stock_consistency",
        ),
        CheckConstraint("status IN ('PUBLISHED', 'TEMPORARILY_HIDDEN', 'DELETED')", name="ck_community_posts_status"),
        CheckConstraint("removed_reason IS NULL OR removed_reason IN ('USER_DELETED', 'MODERATION')", name="ck_community_posts_removed_reason"),
        CheckConstraint("post_type IN ('STOCK', 'GENERAL_MARKET')", name="ck_community_posts_post_type"),
        Index("ix_community_posts_author_created", "author_id", "created_at"),
        Index("ix_community_posts_author_status_created", "author_id", "status", "created_at"),
        Index("ix_community_posts_stock_created", "stock_symbol", "created_at"),
        Index("ix_community_posts_status_created", "status", "created_at"),
        Index("ix_community_posts_type_created", "post_type", "created_at"),
        Index("ix_community_posts_created_id", "created_at", "id"),
        Index("ix_community_posts_status_created_id", "status", "created_at", "id"),
    )


class CommunityPostTicker(Base):
    """Junction table for fast O(1) indexed ticker feeds and multi-cashtag queries."""
    __tablename__ = "community_post_tickers"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    ticker: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    post = relationship("CommunityPost", back_populates="tickers", lazy="select")

    __table_args__ = (
        UniqueConstraint("post_id", "ticker", name="uq_community_post_tickers_post_ticker"),
        Index("ix_community_post_tickers_ticker_created", "ticker", "created_at"),
        Index("ix_community_post_tickers_ticker_id", "ticker", "post_id"),
    )


class CommunityBookmark(Base):
    __tablename__ = "community_bookmarks"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    post = relationship("CommunityPost", back_populates="bookmarks", lazy="select")
    user = relationship("User", lazy="select")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_bookmarks_post_user"),
        Index("ix_community_bookmarks_user_created", "user_id", "created_at"),
    )


class CommunityPostLike(Base):
    __tablename__ = "community_post_likes"

    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    post = relationship("CommunityPost", back_populates="likes", lazy="select")
    user = relationship("User", lazy="select")

    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_community_post_likes_post_user"),
        Index("ix_community_post_likes_user_created", "user_id", "created_at"),
    )


class CommunityComment(Base):
    __tablename__ = "community_comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    parent_comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    content: Mapped[str] = mapped_column(Text, nullable=False)
    reply_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=CommentStatus.PUBLISHED.value, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    post = relationship("CommunityPost", back_populates="comments", lazy="select")
    author = relationship("User", lazy="selectin")
    parent = relationship("CommunityComment", remote_side=[id], backref="replies", lazy="select")
    reports = relationship("CommunityReport", back_populates="comment", lazy="select", cascade="all, delete-orphan")
    moderation_actions = relationship("CommunityModerationAction", back_populates="comment", lazy="select", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("status IN ('PUBLISHED', 'DELETED')", name="ck_community_comments_status"),
        Index("ix_community_comments_post_created", "post_id", "created_at"),
        Index("ix_community_comments_post_parent_created", "post_id", "parent_comment_id", "created_at", "id"),
        Index("ix_community_comments_author_created", "author_id", "created_at"),
    )


class CommunityFollow(Base):
    __tablename__ = "community_follows"

    follower_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    following_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    follower = relationship("User", foreign_keys=[follower_id], lazy="selectin")
    following = relationship("User", foreign_keys=[following_id], lazy="selectin")

    __table_args__ = (
        UniqueConstraint("follower_id", "following_id", name="uq_community_follows_follower_following"),
        CheckConstraint("follower_id != following_id", name="ck_community_follows_no_self_follow"),
        Index("ix_community_follows_follower_created", "follower_id", "created_at"),
        Index("ix_community_follows_following_created", "following_id", "created_at"),
    )


class CommunityReport(Base):
    __tablename__ = "community_reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    reporter_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    post_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    reason: Mapped[str] = mapped_column(String(20), nullable=False)
    status: Mapped[str] = mapped_column(String(20), default=ReportStatus.PENDING.value, nullable=False)
    reviewed_by: Mapped[str | None] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    reporter = relationship("User", foreign_keys=[reporter_id], lazy="select")
    post = relationship("CommunityPost", back_populates="reports", lazy="select")
    comment = relationship("CommunityComment", back_populates="reports", lazy="select")
    reviewer = relationship("User", foreign_keys=[reviewed_by], lazy="select")

    __table_args__ = (
        CheckConstraint("(post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL)", name="ck_community_reports_single_target"),
        CheckConstraint("reason IN ('SPAM', 'OFF_TOPIC', 'MISLEADING', 'ABUSIVE', 'OTHER')", name="ck_community_reports_reason"),
        CheckConstraint("status IN ('PENDING', 'DISMISSED', 'REVIEWED')", name="ck_community_reports_status"),
        Index("ix_community_reports_status_created", "status", "created_at"),
        Index("ix_community_reports_post_status", "post_id", "status"),
        Index("ix_community_reports_comment_status", "comment_id", "status"),
    )


class CommunityModerationAction(Base):
    __tablename__ = "community_moderation_actions"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    moderator_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id"), nullable=True
    )
    post_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    action: Mapped[str] = mapped_column(String(30), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    moderator = relationship("User", foreign_keys=[moderator_id], lazy="select")
    post = relationship("CommunityPost", back_populates="moderation_actions", lazy="select")
    comment = relationship("CommunityComment", back_populates="moderation_actions", lazy="select")

    __table_args__ = (
        CheckConstraint("action IN ('AUTO_HIDDEN', 'RESTORED', 'POST_DELETED', 'COMMENT_DELETED', 'DIRECT_REMOVAL')", name="ck_community_moderation_actions_action"),
        CheckConstraint("(post_id IS NOT NULL AND comment_id IS NULL) OR (post_id IS NULL AND comment_id IS NOT NULL)", name="ck_community_moderation_actions_single_target"),
        Index("ix_community_moderation_actions_post_created", "post_id", "created_at"),
        Index("ix_community_moderation_actions_comment_created", "comment_id", "created_at"),
        Index("ix_community_moderation_actions_moderator_created", "moderator_id", "created_at"),
    )


class CommunityNotification(Base):
    __tablename__ = "community_notifications"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    recipient_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    actor_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    post_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_posts.id", ondelete="CASCADE"), nullable=True, index=True
    )
    comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("community_comments.id", ondelete="CASCADE"), nullable=True, index=True
    )
    type: Mapped[str] = mapped_column(String(40), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    message: Mapped[str] = mapped_column(Text, nullable=False)
    is_read: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )

    recipient = relationship("User", foreign_keys=[recipient_id], lazy="select")
    actor = relationship("User", foreign_keys=[actor_id], lazy="selectin")
    post = relationship("CommunityPost", lazy="select")
    comment = relationship("CommunityComment", lazy="select")

    __table_args__ = (
        CheckConstraint(
            "type IN ('POST_LIKED', 'POST_COMMENTED', 'COMMENT_REPLIED', 'USER_FOLLOWED', 'POST_AUTO_HIDDEN', 'POST_RESTORED', 'POST_MODERATION_DELETED')",
            name="ck_community_notifications_type",
        ),
        Index("ix_community_notifications_recipient_created", "recipient_id", "created_at"),
        Index("ix_community_notifications_recipient_unread", "recipient_id", "is_read"),
        Index("ix_community_notifications_recipient_unread_created", "recipient_id", "is_read", "created_at"),
    )


class CommunityIdempotencyKey(Base):
    __tablename__ = "community_idempotency_keys"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=generate_time_id)
    key: Mapped[str] = mapped_column(String(128), nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(String(36), nullable=False, index=True)
    endpoint: Mapped[str] = mapped_column(String(100), nullable=False)
    response_code: Mapped[int | None] = mapped_column(Integer, nullable=True)
    response_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), default=lambda: datetime.now(timezone.utc)
    )
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "key", name="uq_community_idempotency_user_key"),
        Index("ix_community_idempotency_expires", "expires_at"),
    )