from datetime import datetime
from enum import Enum
from typing import Optional, List, Any, Dict

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


class PostType(str, Enum):
    STOCK = "STOCK"
    GENERAL_MARKET = "GENERAL_MARKET"


class PostStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    TEMPORARILY_HIDDEN = "TEMPORARILY_HIDDEN"
    DELETED = "DELETED"


class RemovedReason(str, Enum):
    USER_DELETED = "USER_DELETED"
    MODERATION = "MODERATION"


class ReportReason(str, Enum):
    SPAM = "SPAM"
    OFF_TOPIC = "OFF_TOPIC"
    MISLEADING = "MISLEADING"
    ABUSIVE = "ABUSIVE"
    OTHER = "OTHER"


class ReportStatus(str, Enum):
    PENDING = "PENDING"
    DISMISSED = "DISMISSED"
    REVIEWED = "REVIEWED"


class CommentStatus(str, Enum):
    PUBLISHED = "PUBLISHED"
    DELETED = "DELETED"


class ModerationActionType(str, Enum):
    AUTO_HIDDEN = "AUTO_HIDDEN"
    RESTORED = "RESTORED"
    POST_DELETED = "POST_DELETED"
    COMMENT_DELETED = "COMMENT_DELETED"
    DIRECT_REMOVAL = "DIRECT_REMOVAL"


class NotificationType(str, Enum):
    POST_LIKED = "POST_LIKED"
    POST_COMMENTED = "POST_COMMENTED"
    COMMENT_REPLIED = "COMMENT_REPLIED"
    USER_FOLLOWED = "USER_FOLLOWED"
    POST_AUTO_HIDDEN = "POST_AUTO_HIDDEN"
    POST_RESTORED = "POST_RESTORED"
    POST_MODERATION_DELETED = "POST_MODERATION_DELETED"


class CommunityAuthorSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    username: str = ""
    full_name: str = ""
    avatar_url: str = ""
    is_verified: bool = False


# Request/Response schemas
class CommunityPostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    post_type: PostType
    stock_symbol: Optional[str] = Field(None, max_length=20)
    image_url: Optional[str] = Field(None, max_length=500)
    image_public_id: Optional[str] = Field(None, max_length=255)
    media_metadata: Optional[str] = None  # JSON string with width, height

    @model_validator(mode="after")
    def validate_content_not_blank(self) -> "CommunityPostCreate":
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be blank")
        self.content = self.content.strip()
        return self

    @model_validator(mode="after")
    def validate_stock_symbol(self) -> "CommunityPostCreate":
        if self.post_type == PostType.STOCK and not self.stock_symbol:
            raise ValueError("stock_symbol is required for STOCK posts")
        if self.post_type == PostType.GENERAL_MARKET and self.stock_symbol:
            raise ValueError("stock_symbol must not be provided for GENERAL_MARKET posts")
        if self.stock_symbol:
            self.stock_symbol = self.stock_symbol.upper()
        return self


class CommunityPostUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)

    @model_validator(mode="after")
    def validate_content_not_blank(self) -> "CommunityPostUpdate":
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be blank")
        self.content = self.content.strip()
        return self


class CommunityPostResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    author_id: str = ""
    author_username: str = ""
    author_full_name: str = ""
    author_avatar_url: str = ""
    author_verified: bool = False
    author: Optional[CommunityAuthorSummary] = None

    post_type: PostType = PostType.GENERAL_MARKET
    stock_symbol: str = ""
    stock_name: str = ""
    tickers: List[str] = Field(default_factory=list)
    price_at_post: Optional[float] = None
    price_snapshot: Optional[float] = None

    content: str = ""
    image_url: str = ""
    media_metadata: Optional[Dict[str, Any]] = None

    like_count: int = 0
    comment_count: int = 0
    report_count: int = 0
    view_count: int = 0
    bookmark_count: int = 0

    is_edited: bool = False
    edited_at: Optional[datetime] = None

    status: PostStatus = PostStatus.PUBLISHED
    removed_reason: str = ""
    liked_by_me: bool = False
    bookmarked_by_me: bool = False
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "author_id", "author_username", "author_full_name", "author_avatar_url", "stock_symbol", "stock_name", "content", "image_url", "removed_reason", mode="before")
    @classmethod
    def _clean_post_str(cls, v):
        if v is None:
            return ""
        if hasattr(v, "value"):
            return str(v.value)
        return str(v)

    @field_validator("like_count", "comment_count", "report_count", "view_count", "bookmark_count", mode="before")
    @classmethod
    def _clean_post_int(cls, v):
        return 0 if v is None else int(v)

    @field_validator("liked_by_me", "bookmarked_by_me", "is_edited", "author_verified", mode="before")
    @classmethod
    def _clean_post_bool(cls, v):
        return False if v is None else bool(v)


class CommunityPostListResponse(BaseModel):
    posts: List[CommunityPostResponse] = Field(default_factory=list)
    cursor: Optional[str] = ""
    next_cursor: Optional[str] = ""
    has_more: bool = False


class CommunityCommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)
    parent_comment_id: Optional[str] = None

    @model_validator(mode="after")
    def validate_content_not_blank(self) -> "CommunityCommentCreate":
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be blank")
        self.content = self.content.strip()
        return self


class CommunityCommentUpdate(BaseModel):
    content: str = Field(..., min_length=1, max_length=2000)

    @model_validator(mode="after")
    def validate_content_not_blank(self) -> "CommunityCommentUpdate":
        if not self.content or not self.content.strip():
            raise ValueError("content cannot be blank")
        self.content = self.content.strip()
        return self


class CommunityCommentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str = ""
    post_id: str = ""
    author_id: str = ""
    author_username: str = ""
    author_full_name: str = ""
    author_avatar_url: str = ""
    author_verified: bool = False
    author: Optional[CommunityAuthorSummary] = None

    parent_comment_id: str = ""
    content: str = ""
    status: CommentStatus = CommentStatus.PUBLISHED
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime

    @field_validator("id", "post_id", "author_id", "author_username", "author_full_name", "author_avatar_url", "parent_comment_id", "content", mode="before")
    @classmethod
    def _clean_comment_str(cls, v):
        return "" if v is None else str(v)

    @field_validator("reply_count", mode="before")
    @classmethod
    def _clean_reply_count(cls, v):
        return 0 if v is None else int(v)


class CommunityCommentListResponse(BaseModel):
    comments: List[CommunityCommentResponse] = Field(default_factory=list)
    cursor: Optional[str] = None
    next_cursor: Optional[str] = None
    has_more: bool = False


class CommunityPostDetailResponse(BaseModel):
    """Fully hydrated post detail response with author, counts, flags, and first page of comments."""
    model_config = ConfigDict(from_attributes=True)

    post: CommunityPostResponse
    comments: List[CommunityCommentResponse] = Field(default_factory=list)
    comments_cursor: Optional[str] = None
    comments_has_more: bool = False


class CommunityFollowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    follower_id: str
    following_id: str
    created_at: datetime


class CommunityFollowStatusResponse(BaseModel):
    is_following: bool
    followers_count: int
    following_count: int


class CommunityFollowListResponse(BaseModel):
    users: List["CommunityUserSummary"]
    cursor: Optional[str] = None
    has_more: bool


class CommunityReportCreate(BaseModel):
    reason: ReportReason
    post_id: Optional[str] = None
    comment_id: Optional[str] = None

    @field_validator("post_id", "comment_id", mode="before")
    @classmethod
    def validate_target(cls, v):
        return v

    def model_post_init(self, __context):
        if (self.post_id is None) == (self.comment_id is None):
            raise ValueError("Exactly one of post_id or comment_id must be provided")


class CommunityReportResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reporter_id: str
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    reason: ReportReason
    status: ReportStatus
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class CommunityReportAdminResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    reporter_id: str
    reporter_username: str
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    post_content: Optional[str] = None
    comment_content: Optional[str] = None
    post_author_id: Optional[str] = None
    post_author_username: Optional[str] = None
    post_type: Optional[PostType] = None
    stock_symbol: Optional[str] = None
    reason: ReportReason
    status: ReportStatus
    reviewed_by: Optional[str] = None
    reviewed_at: Optional[datetime] = None
    created_at: datetime


class CommunityReportStatusUpdate(BaseModel):
    status: ReportStatus


class CommunityModerationActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    moderator_id: Optional[str] = None
    moderator_username: Optional[str] = None
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    action: ModerationActionType
    note: Optional[str] = None
    created_at: datetime


class CommunityUserSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False


class CommunityProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    is_verified: bool = False
    followers_count: int
    following_count: int
    published_post_count: int
    is_following: bool = False
    is_own_profile: bool = False


class CommunityUnifiedProfileResponse(BaseModel):
    """Unified profile screen response: profile info + follow stats + first page of posts."""
    model_config = ConfigDict(from_attributes=True)

    profile: CommunityProfileResponse
    posts: List[CommunityPostResponse] = Field(default_factory=list)
    posts_cursor: Optional[str] = None
    posts_has_more: bool = False


class CommunityNotificationResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    recipient_id: str
    actor_id: Optional[str] = None
    actor_username: Optional[str] = None
    post_id: Optional[str] = None
    comment_id: Optional[str] = None
    type: NotificationType
    title: str
    message: str
    is_read: bool
    created_at: datetime


class CommunityNotificationsListResponse(BaseModel):
    notifications: List[CommunityNotificationResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class FeedQueryParams(BaseModel):
    tab: Optional[str] = Field("for_you", description="Feed tab: for_you, following, or ticker")
    ticker: Optional[str] = None
    stock_symbol: Optional[str] = None
    post_type: Optional[PostType] = None
    search: Optional[str] = None
    q: Optional[str] = None
    mine: bool = False
    following: bool = False
    cursor: Optional[str] = None
    limit: int = Field(20, ge=1, le=50)


class CommunityTrendingResponse(BaseModel):
    trending_tickers: List[Dict[str, Any]] = Field(default_factory=list)
    trending_posts: List[CommunityPostResponse] = Field(default_factory=list)


class MediaUploadUrlRequest(BaseModel):
    filename: str
    content_type: str = Field(..., pattern=r"^(image/jpeg|image/png|image/webp|image/gif)$")
    file_size_bytes: int = Field(..., le=10 * 1024 * 1024)  # Max 10MB


class MediaUploadUrlResponse(BaseModel):
    upload_url: str
    public_id: str
    media_url: str
    fields: Dict[str, str] = Field(default_factory=dict)
    headers: Dict[str, str] = Field(default_factory=dict)


class CommunityStatsResponse(BaseModel):
    total_posts: int
    total_comments: int
    total_likes: int
    total_follows: int
    pending_reports: int