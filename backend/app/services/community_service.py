from datetime import datetime, timedelta

from app.core.exceptions import BadRequestError, NotFoundError, ForbiddenError
from app.models.community import Post
from app.repository.community_repository import CommunityRepository
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    CommentsResponse,
    FeedResponse,
    LeaderboardEntry,
    LeaderboardResponse,
    PostCreate,
    PostResponse,
    ReportCreate,
    ReportResponse,
    VoteResponse,
)

PERIOD_DELTAS = {
    "weekly": timedelta(days=7),
    "monthly": timedelta(days=30),
    "all_time": None,
}


class CommunityService:
    def __init__(self, repo: CommunityRepository):
        self.repo = repo

    async def create_post(self, user_id: str, data: PostCreate) -> PostResponse:
        post = await self.repo.create_post(
            user_id=user_id,
            symbol=data.symbol,
            stance=data.stance,
            rationale_text=data.rationale_text,
        )
        return await self._to_post_response(post, user_id)

    async def get_feed(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        symbol: str | None = None,
    ) -> FeedResponse:
        posts, total = await self.repo.get_feed(page=page, limit=limit, symbol=symbol)
        items = [await self._to_post_response(p, user_id) for p in posts]
        return FeedResponse(
            posts=items,
            total=total,
            page=page,
            limit=limit,
            has_more=(page * limit) < total,
        )

    async def vote(self, user_id: str, post_id: str, direction: str) -> VoteResponse:
        post = await self.repo.get_post(post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")

        if post.user_id == user_id:
            raise BadRequestError("You cannot vote on your own post.")

        vote = await self.repo.upsert_vote(post_id, user_id, direction)

        post = await self.repo.get_post(post_id)
        score = post.upvotes - post.downvotes

        return VoteResponse(
            post_id=post_id,
            direction=direction if vote else None,
            upvotes=post.upvotes,
            downvotes=post.downvotes,
            score=score,
        )

    async def get_comments(self, post_id: str) -> CommentsResponse:
        post = await self.repo.get_post(post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")

        comments = await self.repo.get_comments(post_id)
        items = [self._to_comment_response(c) for c in comments]
        return CommentsResponse(comments=items, total=len(items))

    async def add_comment(self, user_id: str, post_id: str, data: CommentCreate) -> CommentResponse:
        post = await self.repo.get_post(post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")

        comment = await self.repo.create_comment(post_id, user_id, data.text)
        return self._to_comment_response(comment)

    async def get_leaderboard(self, period: str = "all_time") -> LeaderboardResponse:
        if period not in PERIOD_DELTAS:
            raise BadRequestError(f"Invalid period '{period}'. Must be one of: weekly, monthly, all_time")

        since = None
        if PERIOD_DELTAS[period] is not None:
            since = datetime.utcnow() - PERIOD_DELTAS[period]

        entries = await self.repo.get_leaderboard(since=since)
        items = [LeaderboardEntry(**e) for e in entries]

        return LeaderboardResponse(period=period, entries=items)

    async def report_post(self, user_id: str, post_id: str, data: ReportCreate) -> ReportResponse:
        post = await self.repo.get_post(post_id)
        if post is None:
            raise NotFoundError(f"Post '{post_id}' not found.")

        if post.user_id == user_id:
            raise BadRequestError("You cannot report your own post.")

        report = await self.repo.create_report(post_id, user_id, data.reason)
        return ReportResponse(
            id=report.id,
            post_id=report.post_id,
            user_id=report.user_id,
            reason=report.reason,
            created_at=report.created_at,
        )

    async def _to_post_response(self, post: Post, viewer_id: str) -> PostResponse:
        user_vote = await self.repo.get_user_vote(post.id, viewer_id)
        username = post.author.username if post.author else None

        return PostResponse(
            id=post.id,
            user_id=post.user_id,
            username=username,
            symbol=post.symbol,
            stance=post.stance,
            rationale_text=post.rationale_text,
            upvotes=post.upvotes,
            downvotes=post.downvotes,
            score=post.upvotes - post.downvotes,
            comment_count=post.comment_count,
            user_vote=user_vote.direction if user_vote else None,
            created_at=post.created_at,
        )

    def _to_comment_response(self, comment) -> CommentResponse:
        return CommentResponse(
            id=comment.id,
            post_id=comment.post_id,
            user_id=comment.user_id,
            username=comment.author.username if comment.author else None,
            text=comment.text,
            created_at=comment.created_at,
        )
