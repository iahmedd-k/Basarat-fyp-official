import logging

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import AppError, ServiceUnavailableError
from app.core.rate_limiter import limiter
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

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    repo = CommunityRepository(db)
    return CommunityService(repo=repo)


@router.get(
    "/community/feed",
    response_model=FeedResponse,
    summary="Get community post feed with optional filters",
)
@limiter.limit("30/minute")
async def get_feed(
    request: Request,
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    symbol: str | None = Query(None),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_feed(user_id=user.id, page=page, limit=limit, symbol=symbol)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch feed")
        raise ServiceUnavailableError("Feed temporarily unavailable.")


@router.post(
    "/community/posts",
    response_model=PostResponse,
    status_code=201,
    summary="Create a new post (bullish/bearish stance)",
)
@limiter.limit("10/minute")
async def create_post(
    request: Request,
    data: PostCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.create_post(user.id, data)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to create post")
        raise ServiceUnavailableError("Failed to create post.")


@router.post(
    "/community/posts/{post_id}/vote",
    response_model=VoteResponse,
    summary="Vote on a post (up or down)",
)
@limiter.limit("20/minute")
async def vote_post(
    request: Request,
    post_id: str,
    data: VoteRequest,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.vote(user.id, post_id, data.direction)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to vote")
        raise ServiceUnavailableError("Failed to vote.")


@router.get(
    "/community/posts/{post_id}/comments",
    response_model=CommentsResponse,
    summary="Get comments for a post",
)
@limiter.limit("30/minute")
async def get_comments(
    request: Request,
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_comments(post_id)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch comments")
        raise ServiceUnavailableError("Failed to fetch comments.")


@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment to a post",
)
@limiter.limit("10/minute")
async def add_comment(
    request: Request,
    post_id: str,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.add_comment(user.id, post_id, data)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to add comment")
        raise ServiceUnavailableError("Failed to add comment.")


@router.get(
    "/community/leaderboard",
    response_model=LeaderboardResponse,
    summary="Get community leaderboard by period",
)
@limiter.limit("30/minute")
async def get_leaderboard(
    request: Request,
    period: str = Query("all_time", pattern="^(weekly|monthly|all_time)$"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_leaderboard(period)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to fetch leaderboard")
        raise ServiceUnavailableError("Failed to fetch leaderboard.")


@router.post(
    "/community/posts/{post_id}/report",
    response_model=ReportResponse,
    status_code=201,
    summary="Report a post for moderation",
)
@limiter.limit("3/minute")
async def report_post(
    request: Request,
    post_id: str,
    data: ReportCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.report_post(user.id, post_id, data)
    except AppError:
        raise
    except Exception:
        logger.exception("Failed to report post")
        raise ServiceUnavailableError("Failed to report post.")
