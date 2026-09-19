from datetime import datetime, timezone
from uuid import uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Post(Base):
    """A community post tagged to 1-3 real stock tickers."""

    __tablename__ = "posts"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), index=True, nullable=False)
    content: Mapped[str] = mapped_column(String(500), nullable=False)
    sentiment: Mapped[str | None] = mapped_column(String(10), nullable=True)
    media_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    like_count: Mapped[int] = mapped_column(default=0, nullable=False)
    comment_count: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PUBLISHED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    author = relationship("User", back_populates="posts", lazy="selectin")
    comments = relationship("Comment", back_populates="post", lazy="noload", cascade="all, delete-orphan")
    likes = relationship("PostLike", back_populates="post", lazy="noload", cascade="all, delete-orphan")
    tags = relationship("PostStockTag", back_populates="post", lazy="noload", cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint("sentiment IN ('BULLISH','BEARISH','NEUTRAL')", name="ck_posts_sentiment"),
        CheckConstraint("status IN ('PUBLISHED','REMOVED','FLAGGED')", name="ck_posts_status"),
        CheckConstraint("length(content) BETWEEN 1 AND 500", name="ck_posts_content_len"),
    )


class PostStockTag(Base):
    """Which real stocks a post is tagged to (1-3 rows per post)."""

    __tablename__ = "post_stock_tags"

    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    symbol: Mapped[str] = mapped_column(String(10), ForeignKey("stocks.symbol"), primary_key=True)

    post = relationship("Post", back_populates="tags")

    __table_args__ = (
        Index("idx_post_stock_tags_symbol", "symbol"),
    )


class PostLike(Base):
    """Like toggle — unique (post_id, user_id)."""

    __tablename__ = "post_likes"

    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), primary_key=True
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    post = relationship("Post", back_populates="likes")


class Comment(Base):
    """Comment on a post — max depth 2 (top-level + one level of replies)."""

    __tablename__ = "comments"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), index=True, nullable=False
    )
    user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    parent_comment_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("comments.id"), nullable=True
    )
    content: Mapped[str] = mapped_column(String(300), nullable=False)
    like_count: Mapped[int] = mapped_column(default=0, nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PUBLISHED", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    post = relationship("Post", back_populates="comments")
    author = relationship("User", lazy="selectin")

    __table_args__ = (
        Index("idx_comments_post_id", "post_id"),
        CheckConstraint("status IN ('PUBLISHED','REMOVED')", name="ck_comments_status"),
        CheckConstraint("length(content) BETWEEN 1 AND 300", name="ck_comments_content_len"),
    )


class Report(Base):
    """Moderation report against a post or a comment (polymorphic target)."""

    __tablename__ = "reports"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: uuid4().hex)
    reporter_user_id: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    target_type: Mapped[str] = mapped_column(String(10), nullable=False)
    target_id: Mapped[str] = mapped_column(String(36), nullable=False)
    reason: Mapped[str] = mapped_column(String(50), nullable=False)
    status: Mapped[str] = mapped_column(String(12), default="PENDING", nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    __table_args__ = (
        UniqueConstraint("reporter_user_id", "target_type", "target_id", name="uq_reports_reporter_target"),
        Index("idx_reports_target", "target_type", "target_id"),
        CheckConstraint("target_type IN ('POST','COMMENT')", name="ck_reports_target_type"),
        CheckConstraint("status IN ('PENDING','REVIEWED','DISMISSED')", name="ck_reports_status"),
        CheckConstraint(
            "reason IN ('SPAM','MISLEADING_INFO','HARASSMENT','OFF_TOPIC','OTHER')",
            name="ck_reports_reason",
        ),
    )


class ShareLink(Base):
    """Short share deep-link for a post."""

    __tablename__ = "share_links"

    short_code: Mapped[str] = mapped_column(String(12), primary_key=True)
    post_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("posts.id", ondelete="CASCADE"), nullable=False
    )
    created_by: Mapped[str] = mapped_column(String(36), ForeignKey("users.id"), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        default=lambda: datetime.now(timezone.utc),
        nullable=False,
    )