import logging
import re

from fastapi import APIRouter, Depends, File, Query, UploadFile
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import CommunityError
from app.db.session import get_db
from app.models.user import User
from app.repository.community_repository import CommunityRepository
from app.schemas.community import (
    CommentCreate,
    CommentResponse,
    CommentsResponse,
    FeedItem,
    FeedResponse,
    LikeResponse,
    MediaUploadResponse,
    PostCreate,
    PostCreatedResponse,
    ReportCreate,
    ReportResponse,
    ShareLinkResponse,
    ShareResolveResponse,
)
from app.services.community_service import CommunityService
from app.services.media_service import MediaService
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

router = APIRouter()

_SYMBOL_PATTERN = re.compile(r"^[A-Za-z][A-Za-z0-9]{1,9}$")


def _get_service(
    db: AsyncSession = Depends(get_db),
    stock_service: StockService = Depends(StockService),
) -> CommunityService:
    return CommunityService(repo=CommunityRepository(db), stock_service=stock_service)


def _validate_symbol(symbol: str) -> str:
    symbol = symbol.strip().upper()
    if not _SYMBOL_PATTERN.match(symbol):
        raise CommunityError(
            400,
            "INVALID_STOCK_TAG",
            f"Symbol '{symbol}' is not a recognized ticker.",
            field="symbols",
        )
    return symbol


# ── 4.1 Create post ────────────────────────────────────────────────────────
@router.post(
    "/community/posts",
    response_model=PostCreatedResponse,
    status_code=201,
    summary="Create a post tagged to 1-3 real stock tickers",
)
async def create_post(
    data: PostCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.create_post(user.id, data)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Create post failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to create post.")


# ── 4.1b Upload post media (Cloudinary) ─────────────────────────────────────
@router.post(
    "/community/media",
    response_model=MediaUploadResponse,
    status_code=201,
    summary="Upload a post image to Cloudinary and get a media URL to attach",
)
async def upload_media(
    file: UploadFile = File(..., description="JPEG/PNG/WebP/GIF/BMP/HEIC image"),
    user: User = Depends(get_current_user),
    media_service: MediaService = Depends(MediaService),
):
    try:
        content = await file.read()
    except Exception:
        logger.exception("Reading uploaded media failed")
        raise CommunityError(400, "INVALID_IMAGE", "Could not read the uploaded file.", field="image")
    try:
        return await media_service.upload_image(content, original_name=file.filename or "post.jpg")
    except CommunityError:
        raise
    except Exception:
        logger.exception("Media upload failed unexpectedly")
        raise CommunityError(
            503, "MEDIA_UPLOAD_UNAVAILABLE", "Media upload service is unavailable.", field="image"
        )


# ── 4.2 Get feed (global) ──────────────────────────────────────────────────
@router.get(
    "/community/feed",
    response_model=FeedResponse,
    summary="Get the global community feed",
)
async def get_feed(
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    filter: str = Query("all", pattern="^(all|following)$"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_feed(user.id, cursor=cursor, limit=limit, filter=filter)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Get feed failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Feed temporarily unavailable.")


# ── 4.3 Get posts for a specific stock ─────────────────────────────────────
@router.get(
    "/community/stocks/{symbol}/posts",
    response_model=FeedResponse,
    summary="Get posts tagged to a specific stock",
)
async def get_stock_posts(
    symbol: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        symbol = _validate_symbol(symbol)
        return await service.get_stock_posts(user.id, symbol, cursor=cursor, limit=limit)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Get stock posts failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Feed temporarily unavailable.")


# ── 4.4 Get single post ────────────────────────────────────────────────────
@router.get(
    "/community/posts/{post_id}",
    response_model=FeedItem,
    summary="Get a single post",
)
async def get_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_post(user.id, post_id)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Get post failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Post temporarily unavailable.")


# ── 4.5 Delete post (owner only, soft delete) ──────────────────────────────
@router.delete(
    "/community/posts/{post_id}",
    status_code=204,
    summary="Delete your own post (soft delete)",
)
async def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.delete_post(user.id, post_id)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Delete post failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to delete post.")


# ── 4.6 Like / unlike (toggle) ─────────────────────────────────────────────
@router.post(
    "/community/posts/{post_id}/like",
    response_model=LikeResponse,
    summary="Toggle a like on a post",
)
async def toggle_like(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.toggle_like(user.id, post_id)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Toggle like failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to update like.")


# ── 4.7 Add comment ────────────────────────────────────────────────────────
@router.post(
    "/community/posts/{post_id}/comments",
    response_model=CommentResponse,
    status_code=201,
    summary="Add a comment or reply to a top-level comment",
)
async def add_comment(
    post_id: str,
    data: CommentCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.add_comment(user.id, post_id, data)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Add comment failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to add comment.")


# ── 4.8 Get comments for a post ────────────────────────────────────────────
@router.get(
    "/community/posts/{post_id}/comments",
    response_model=CommentsResponse,
    summary="Get comments for a post (with one level of nested replies)",
)
async def get_comments(
    post_id: str,
    cursor: str | None = Query(None),
    limit: int = Query(20, ge=1, le=50),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.get_comments(post_id, cursor=cursor, limit=limit)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Get comments failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to fetch comments.")


# ── 4.9 Report post or comment ─────────────────────────────────────────────
@router.post(
    "/community/reports",
    response_model=ReportResponse,
    status_code=201,
    summary="Report a post or comment",
)
async def create_report(
    data: ReportCreate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.create_report(user.id, data.targetType, data.targetId, data.reason)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Create report failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to submit report.")


# ── 4.10 Create share link ─────────────────────────────────────────────────
@router.post(
    "/community/posts/{post_id}/share",
    response_model=ShareLinkResponse,
    status_code=201,
    summary="Create a share deep-link for a post",
)
async def create_share_link(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.create_share_link(user.id, post_id)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Create share link failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to create share link.")


# ── 4.11 Resolve share link (public, no auth, teaser only) ─────────────────
@router.get(
    "/community/share/{short_code}",
    response_model=ShareResolveResponse,
    summary="Resolve a share link — public, never exposes post content",
)
async def resolve_share_link(
    short_code: str,
    service: CommunityService = Depends(_get_service),
):
    try:
        return await service.resolve_share_link(short_code)
    except CommunityError:
        raise
    except Exception:
        logger.exception("Resolve share link failed unexpectedly")
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Failed to resolve share link.")