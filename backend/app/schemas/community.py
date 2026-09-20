from datetime import datetime
from enum import Enum
from typing import Optional, List

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


# Request/Response schemas
class CommunityPostCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=5000)
    post_type: PostType
    stock_symbol: Optional[str] = Field(None, max_length=20)

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

    id: str
    author_id: str
    author_username: Optional[str] = None
    author_full_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    post_type: PostType
    stock_symbol: Optional[str] = None
    stock_name: Optional[str] = None
    content: str
    image_url: Optional[str] = None
    like_count: int
    comment_count: int
    report_count: int
    status: PostStatus
    removed_reason: Optional[RemovedReason] = None
    liked_by_me: bool = False
    created_at: datetime
    updated_at: datetime


class CommunityPostListResponse(BaseModel):
    posts: List[CommunityPostResponse]
    cursor: Optional[str] = None
    has_more: bool


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

    id: str
    post_id: str
    author_id: str
    author_username: Optional[str] = None
    author_full_name: Optional[str] = None
    author_avatar_url: Optional[str] = None
    parent_comment_id: Optional[str] = None
    content: str
    status: CommentStatus
    reply_count: int = 0
    created_at: datetime
    updated_at: datetime


class CommunityCommentListResponse(BaseModel):
    comments: List[CommunityCommentResponse]
    cursor: Optional[str] = None
    has_more: bool


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


class CommunityProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    username: str
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None
    followers_count: int
    following_count: int
    published_post_count: int
    is_following: bool = False
    is_own_profile: bool = False


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
    stock_symbol: Optional[str] = None
    post_type: Optional[PostType] = None
    mine: bool = False
    following: bool = False
    cursor: Optional[str] = None
    limit: int = Field(20, ge=1, le=50)


class CommunityStatsResponse(BaseModel):
    total_posts: int
    total_comments: int
    total_likes: int
    total_follows: int
    pending_reports: int