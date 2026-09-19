import re
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field, field_validator

_CLOUDINARY_URL_RE = re.compile(
    r"^https://res\.cloudinary\.com/[^/]+/image/upload/", re.IGNORECASE
)


def to_iso_z(dt: datetime | None) -> str | None:
    """Serialize a datetime to the contract's UTC 'Z' format."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class PostCreate(BaseModel):
    content: str = Field(..., max_length=500, description="Post text content (1-500 chars).")
    symbols: list[str] = Field(
        default_factory=list,
        description="1-3 real stock tickers (validated against the stocks table).",
    )
    sentiment: Literal["BULLISH", "BEARISH", "NEUTRAL"] | None = None
    mediaUrl: str | None = Field(
        None,
        description="Cloudinary image URL returned by POST /community/media.",
    )

    @field_validator("content")
    @classmethod
    def _strip_content(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("content must not be empty")
        return v

    @field_validator("symbols")
    @classmethod
    def _normalize_symbols(cls, v: list[str]) -> list[str]:
        normalized = []
        for s in v or []:
            s = (s or "").strip().upper()
            if not s:
                raise ValueError("symbols must contain non-empty tickers")
            normalized.append(s)
        return normalized

    @field_validator("mediaUrl")
    @classmethod
    def _validate_media_url(cls, v: str | None) -> str | None:
        if v is None:
            return None
        v = v.strip()
        if not _CLOUDINARY_URL_RE.match(v):
            raise ValueError(
                "mediaUrl must be a Cloudinary media URL returned by POST /community/media"
            )
        return v


class FeedUser(BaseModel):
    id: str
    username: str
    avatarUrl: str | None = None


class FeedSymbolQuote(BaseModel):
    symbol: str
    price: float
    changePercent: float


class PostCreatedResponse(BaseModel):
    id: str
    userId: str
    content: str
    symbols: list[str]
    sentiment: str | None = None
    mediaUrl: str | None = None
    likeCount: int
    commentCount: int
    likedByMe: bool
    createdAt: str


class FeedItem(BaseModel):
    id: str
    user: FeedUser
    content: str
    symbols: list[FeedSymbolQuote]
    sentiment: str | None = None
    mediaUrl: str | None = None
    likeCount: int
    commentCount: int
    likedByMe: bool
    createdAt: str


class FeedResponse(BaseModel):
    items: list[FeedItem]
    nextCursor: str | None = None


class LikeResponse(BaseModel):
    postId: str
    likedByMe: bool
    likeCount: int


class MediaUploadResponse(BaseModel):
    url: str
    publicId: str


class CommentCreate(BaseModel):
    content: str = Field(..., max_length=300, description="Comment text (1-300 chars).")
    parentCommentId: str | None = Field(None, description="Reply to a top-level comment.")

    @field_validator("content")
    @classmethod
    def _strip_content(cls, v: str) -> str:
        v = (v or "").strip()
        if not v:
            raise ValueError("content must not be empty")
        return v


class CommentResponse(BaseModel):
    """Single comment (create-comment response)."""

    id: str
    postId: str
    user: FeedUser
    content: str
    parentCommentId: str | None = None
    likeCount: int
    createdAt: str


class CommentReplyResponse(BaseModel):
    id: str
    user: FeedUser
    content: str
    likeCount: int
    createdAt: str


class CommentItem(BaseModel):
    """Comment item in the list response, with nested replies."""

    id: str
    user: FeedUser
    content: str
    likeCount: int
    createdAt: str
    replies: list[CommentReplyResponse] = []


class CommentsResponse(BaseModel):
    items: list[CommentItem]
    nextCursor: str | None = None


class ReportCreate(BaseModel):
    targetType: Literal["POST", "COMMENT"]
    targetId: str = Field(..., min_length=1)
    reason: Literal["SPAM", "MISLEADING_INFO", "HARASSMENT", "OFF_TOPIC", "OTHER"]


class ReportResponse(BaseModel):
    id: str
    status: str


class ShareLinkResponse(BaseModel):
    shortUrl: str
    shortCode: str


class ShareResolveResponse(BaseModel):
    postId: str
    deepLink: str
    androidPackage: str
    playStoreUrl: str
    teaser: dict