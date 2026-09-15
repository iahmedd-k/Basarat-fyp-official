from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import ServiceUnavailableError
from app.db.session import get_db
from app.models.user import User
from app.repository.community_repository import CommunityRepository
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    CommentsResponse,
    FeedResponse,
    LeaderboardResponse,
    PostCreate,
    PostResponse,
    ReportCreate,
    ReportResponse,
    VoteRequest,
    VoteResponse,
)
from app.services.community_service import CommunityService

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    repo = CommunityRepository(db)
    return CommunityService(repo=repo)


@router.get(
    "/community/feed",
    response_model=FeedResponse,
    summary="Get community post feed with optional filters",
)
async def get_feed(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    symbol: str | None = Query(None),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_feed(user_id=user.id, page=page, limit=limit, symbol=symbol)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch feed: {exc}")


@router.post(
    "/community/posts",
    response_model=PostResponse,
    status_code=201,
    summary="Create a new post (bullish/bearish stance)",
)
async def create_post(
    data: PostCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.create_post(user.id, data)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to create post: {exc}")


@router.post(
    "/community/posts/{post_id}/vote",
    response_model=VoteResponse,
    summary="Vote on a post (up or down)",
)
async def vote_post(
    post_id: str,
    data: VoteRequest,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.vote(user.id, post_id, data.direction)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to vote: {exc}")


@router.get(
    "/community/posts/{post_id}/comments",
    response_model=CommentsResponse,
    summary="Get comments for a post",
)
async def get_comments(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_comments(post_id)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch comments: {exc}")


@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment to a post",
)
async def add_comment(
    post_id: str,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.add_comment(user.id, post_id, data)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to add comment: {exc}")


@router.get(
    "/community/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get community leaderboard by period",
)
async def get_leaderboard(
    period: str = Query("all_time", pattern="^(weekly|monthly|all_time)$"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_leaderboard(period)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch leaderboard: {exc}")


@router.post(
    "/community/posts/{post_id}/report",
    response_model=ReportResponse,
    status_code=201,
    summary="Report a post for moderation",
)
async def report_post(
    post_id: str,
    data: ReportCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.report_post(user.id, post_id, data)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to report post: {exc}")
