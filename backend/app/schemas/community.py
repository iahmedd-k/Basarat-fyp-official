from datetime import datetime
from pydantic import BaseModel, Field


class PostCreate(BaseModel):
    symbol: str = Field(..., min_length=1, max_length=20, examples=["HBL"])
    stance: str = Field(..., pattern="^(bullish|bearish)$", examples=["bullish"])
    rationale_text: str = Field(..., min_length=10, max_length=5000, examples=["Strong fundamentals..."])


class PostResponse(BaseModel):
    id: str
    user_id: str
    username: str | None = None
    symbol: str
    stance: str
    rationale_text: str
    upvotes: int
    downvotes: int
    score: int
    comment_count: int
    user_vote: str | None = None
    created_at: datetime

    model_config = {"from_attributes": True}


class FeedResponse(BaseModel):
    posts: list[PostResponse]
    total: int
    page: int
    limit: int
    has_more: bool


class VoteRequest(BaseModel):
    direction: str = Field(..., pattern="^(up|down)$")


class VoteResponse(BaseModel):
    post_id: str
    direction: str | None = None
    upvotes: int
    downvotes: int
    score: int


class CommentCreate(BaseModel):
    text: str = Field(..., min_length=1, max_length=2000, examples=["Great analysis!"])


class CommentResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    username: str | None = None
    text: str
    created_at: datetime

    model_config = {"from_attributes": True}


class CommentsResponse(BaseModel):
    comments: list[CommentResponse]
    total: int


class LeaderboardEntry(BaseModel):
    user_id: str
    username: str | None = None
    avatar_url: str | None = None
    post_count: int
    total_score: int
    upvotes_received: int
    rank: int


class LeaderboardResponse(BaseModel):
    period: str
    entries: list[LeaderboardEntry]


class ReportCreate(BaseModel):
    reason: str = Field(..., min_length=5, max_length=1000, examples=["Spam content"])


class ReportResponse(BaseModel):
    id: str
    post_id: str
    user_id: str
    reason: str
    created_at: datetime
