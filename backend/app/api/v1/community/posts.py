import hashlib
import json
import logging
from typing import Optional, List
from fastapi import APIRouter, Depends, UploadFile, File, Form, Query, Request, Header, Response, status
from sqlalchemy import select
from sqlalchemy.orm import joinedload, selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.rate_limiter import limiter
from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ServiceUnavailableError,
    ValidationFailedError,
)
from app.db.session import get_db
from app.models.user import User
from app.models.community import CommunityPost
from app.schemas.community import (
    CommunityPostCreate,
    CommunityPostUpdate,
    CommunityPostResponse,
    CommunityPostListResponse,
    CommunityPostDetailResponse,
    CommunityCommentResponse,
    CommunityAuthorSummary,
    CommunityTrendingResponse,
    FeedQueryParams,
    PostType,
    PostStatus,
)
from app.services.community_service import CommunityService
from app.services.cloudinary_service import cloudinary_service
from app.services.idempotency_service import IdempotencyService
from app.services.trending_service import TrendingService

router = APIRouter()
log = logging.getLogger(__name__)


async def _get_service(db: AsyncSession = Depends(get_db)) -> CommunityService:
    return CommunityService(db)


def _build_post_response(
    post,
    liked_by_me: bool = False,
    bookmarked_by_me: bool = False,
    author=None,
) -> CommunityPostResponse:
    # Extract ticker symbols
    tickers = []
    if hasattr(post, "tickers") and post.tickers:
        tickers = [t.ticker for t in post.tickers]
    elif post.stock_symbol:
        tickers = [post.stock_symbol]

    # Parse media metadata
    media_meta = None
    if post.media_metadata:
        try:
            media_meta = json.loads(post.media_metadata) if isinstance(post.media_metadata, str) else post.media_metadata
        except Exception:
            pass

    author_user = author if author is not None else getattr(post, "author", None)
    author_obj = None
    if author_user:
        author_obj = CommunityAuthorSummary(
            id=author_user.id,
            username=author_user.username,
            full_name=author_user.full_name or "",
            avatar_url=author_user.avatar_url or "",
            is_verified=getattr(author_user, "is_verified", False),
        )

    return CommunityPostResponse(
        id=post.id,
        author_id=post.author_id,
        author_username=author_user.username if author_user else "",
        author_full_name=author_user.full_name if author_user else "",
        author_avatar_url=author_user.avatar_url if author_user else "",
        author_verified=getattr(author_user, "is_verified", False) if author_user else False,
        author=author_obj,
        post_type=PostType(post.post_type),
        stock_symbol=post.stock_symbol or "",
        stock_name=post.stock.name if post.stock else "",
        tickers=tickers,
        price_at_post=post.price_at_post,
        price_snapshot=post.price_at_post,
        content=post.content,
        image_url=post.image_url or "",
        media_metadata=media_meta,
        like_count=post.like_count,
        comment_count=post.comment_count,
        report_count=post.report_count,
        view_count=getattr(post, "view_count", 0),
        bookmark_count=getattr(post, "bookmark_count", 0),
        is_edited=getattr(post, "is_edited", False),
        edited_at=getattr(post, "edited_at", None),
        status=PostStatus(post.status) if hasattr(PostStatus, post.status) else PostStatus.PUBLISHED,
        removed_reason=post.removed_reason or "",
        liked_by_me=liked_by_me,
        bookmarked_by_me=bookmarked_by_me,
        created_at=post.created_at,
        updated_at=post.updated_at,
    )


@router.post(
    "/community/posts",
    response_model=CommunityPostResponse,
    status_code=201,
    summary="Create a new community post",
)
@limiter.limit("10/minute")
async def create_post(
    request: Request,
    content: Optional[str] = Form(None),
    post_type: Optional[PostType] = Form(None),
    stock_symbol: Optional[str] = Form(None),
    image_url: Optional[str] = Form(None),
    image_public_id: Optional[str] = Form(None),
    media_metadata: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None),
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    # Check if request is JSON body
    content_type = request.headers.get("content-type", "")
    if "application/json" in content_type:
        try:
            body_json = await request.json()
            if body_json and isinstance(body_json, dict):
                content = body_json.get("content", content)
                raw_pt = body_json.get("post_type")
                if raw_pt:
                    try:
                        post_type = PostType(str(raw_pt).upper())
                    except Exception:
                        post_type = PostType(raw_pt)
                stock_symbol = body_json.get("stock_symbol", stock_symbol)
                image_url = body_json.get("image_url", image_url)
                image_public_id = body_json.get("image_public_id", image_public_id)
                mm = body_json.get("media_metadata")
                if mm is not None:
                    media_metadata = json.dumps(mm) if isinstance(mm, (dict, list)) else str(mm)
        except Exception:
            pass

    if not content or len(content.strip()) == 0:
        raise ValidationFailedError("content is required")
    if not post_type:
        raise ValidationFailedError("post_type is required")

    # Check Idempotency Key
    if idempotency_key:
        cached_res = await IdempotencyService.get_stored_response(
            service.db, user.id, idempotency_key, "/community/posts"
        )
        if cached_res:
            code, body = cached_res
            return CommunityPostResponse(**body)

    uploaded_public_id = None
    try:
        final_image_url = image_url
        final_image_public_id = image_public_id

        # Direct multipart upload fallback if provided
        if image:
            if not cloudinary_service.is_configured():
                raise ServiceUnavailableError("Image upload service not configured")
            final_image_url, final_image_public_id = await cloudinary_service.upload_image(image)
            uploaded_public_id = final_image_public_id

        post = await service.create_post(
            author_id=user.id,
            content=content,
            post_type=post_type,
            stock_symbol=stock_symbol.upper() if stock_symbol else None,
            image_url=final_image_url,
            image_public_id=final_image_public_id,
            media_metadata=media_metadata,
        )

        post_data = await service.get_post_with_details(post.id, current_user_id=user.id)
        post_obj = post_data["post"]
        response_model = _build_post_response(
            post_obj,
            liked_by_me=post_data["liked_by_me"],
            bookmarked_by_me=post_data["bookmarked_by_me"],
        )

        # Record Idempotency Key
        if idempotency_key:
            await IdempotencyService.record_response(
                service.db,
                user.id,
                idempotency_key,
                "/community/posts",
                201,
                response_model.model_dump(mode="json"),
            )

        return response_model
    except (ValidationFailedError, ConflictError, NotFoundError, BadRequestError):
        if uploaded_public_id:
            await cloudinary_service.delete_image(uploaded_public_id)
        raise
    except Exception:
        if uploaded_public_id:
            await cloudinary_service.delete_image(uploaded_public_id)
        log.exception("Create post failed")
        raise ServiceUnavailableError("Failed to create post")


from app.core.redis import cache_get, cache_set, cache_invalidate

@router.get(
    "/community/posts",
    response_model=CommunityPostListResponse,
    summary="Get community posts / feed alias",
)
@router.get(
    "/community/feed",
    response_model=CommunityPostListResponse,
    summary="Get community feed with unified tabs, search, and batched hydration",
)
async def get_feed(
    request: Request,
    response: Response,
    tab: Optional[str] = Query("for_you", description="Feed tab: for_you, following, or ticker"),
    ticker: Optional[str] = Query(None, description="Ticker symbol for ticker tab (e.g. OGDC)"),
    stock_symbol: Optional[str] = Query(None, description="Filter by stock symbol"),
    post_type: Optional[PostType] = Query(None, description="Filter by post type: STOCK or GENERAL_MARKET"),
    q: Optional[str] = Query(None, description="Search keyword, symbol, or cashtag"),
    search: Optional[str] = Query(None, description="Alias for search query"),
    author_username: Optional[str] = Query(None, description="Filter by author username"),
    mine: bool = Query(False, description="Filter to current user's posts"),
    following: bool = Query(False, description="Filter to followed authors"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    if_none_match: Optional[str] = Header(None, alias="If-None-Match"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        effective_stock = ticker or stock_symbol
        is_following_tab = following or (tab == "following")
        search_query = q or search

        cache_key = f"community:feed:{user.id}:{tab}:{effective_stock}:{post_type}:{search_query}:{author_username}:{mine}:{is_following_tab}:{cursor}:{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return CommunityPostListResponse(**cached)

        posts, next_cursor, has_more = await service.get_feed(
            current_user_id=user.id,
            stock_symbol=effective_stock,
            post_type=post_type,
            search_query=search_query,
            author_username=author_username,
            mine=mine,
            following=is_following_tab,
            cursor=cursor,
            limit=limit,
        )

        # Batch fetch all liked and bookmarked statuses in ONE query (Kills N+1 completely!)
        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        result = CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
        await cache_set(cache_key, result.model_dump(mode="json"), ttl_seconds=30)

        # ETag calculation for caching / 304 Not Modified support
        if posts:
            etag_raw = f"{posts[0].id}_{len(posts)}_{posts[0].updated_at.isoformat()}"
            computed_etag = f'"{hashlib.md5(etag_raw.encode("utf-8")).hexdigest()}"'
            response.headers["ETag"] = computed_etag
            response.headers["Cache-Control"] = "private, max-age=5, stale-while-revalidate=15"

            if if_none_match and if_none_match == computed_etag:
                response.status_code = status.HTTP_304_NOT_MODIFIED
                return Response(status_code=status.HTTP_304_NOT_MODIFIED, headers=dict(response.headers))

        return result
    except Exception:
        log.exception("Get feed failed")
        raise ServiceUnavailableError("Failed to get feed")


@router.get(
    "/community/trending",
    response_model=CommunityTrendingResponse,
    summary="Get trending tickers and ranked posts",
)
async def get_trending(
    limit: int = Query(10, ge=1, le=30),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    """Fetch trending cashtags and ranked viral discussions."""
    try:
        cache_key = f"community:trending_full:{user.id}:{limit}"
        cached = await cache_get(cache_key)
        if cached is not None:
            return CommunityTrendingResponse(**cached)

        trending_tickers = await TrendingService.get_trending_tickers(service.db, limit=limit)
        trending_post_ids = await TrendingService.get_trending_posts(service.db, limit=limit)

        posts = []
        if trending_post_ids:
            liked_set, bookmarked_set = await service.batch_fetch_post_interactions(trending_post_ids, user.id)
            
            stmt = (
                select(CommunityPost)
                .options(
                    joinedload(CommunityPost.author),
                    joinedload(CommunityPost.stock),
                    selectinload(CommunityPost.tickers),
                )
                .where(
                    CommunityPost.id.in_(trending_post_ids),
                    CommunityPost.status == PostStatus.PUBLISHED.value,
                )
            )
            result = await service.db.execute(stmt)
            db_posts_map = {p.id: p for p in result.scalars().all()}

            for pid in trending_post_ids:
                if pid in db_posts_map:
                    posts.append(
                        _build_post_response(
                            db_posts_map[pid],
                            liked_by_me=pid in liked_set,
                            bookmarked_by_me=pid in bookmarked_set,
                        )
                    )

        res = CommunityTrendingResponse(
            trending_tickers=trending_tickers,
            trending_posts=posts,
        )
        await cache_set(cache_key, res.model_dump(mode="json"), ttl_seconds=60)
        return res
    except Exception:
        log.exception("Get trending failed")
        raise ServiceUnavailableError("Failed to get trending data")


@router.get(
    "/community/posts/search",
    response_model=CommunityPostListResponse,
    summary="Search community posts with multi-factor filters",
)
async def search_posts(
    q: Optional[str] = Query(None, description="Search text query across post content and symbols"),
    search: Optional[str] = Query(None, description="Alias for search query"),
    stock_symbol: Optional[str] = Query(None, description="Filter by stock ticker symbol"),
    post_type: Optional[PostType] = Query(None, description="Filter by post type (STOCK or GENERAL_MARKET)"),
    author_username: Optional[str] = Query(None, description="Filter by author username"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        search_query = q or search
        posts, next_cursor, has_more = await service.get_feed(
            current_user_id=user.id,
            stock_symbol=stock_symbol,
            post_type=post_type,
            search_query=search_query,
            author_username=author_username,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
    except Exception:
        log.exception("Search posts failed")
        raise ServiceUnavailableError("Failed to search community posts")


@router.get(
    "/community/posts/market",
    response_model=CommunityPostListResponse,
    summary="Get general market community posts",
)
async def get_market_posts(
    q: Optional[str] = Query(None, description="Optional search query within general market posts"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        posts, next_cursor, has_more = await service.get_feed(
            current_user_id=user.id,
            post_type=PostType.GENERAL_MARKET,
            search_query=q,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
    except Exception:
        log.exception("Get market posts failed")
        raise ServiceUnavailableError("Failed to get market posts")


@router.get(
    "/community/posts/stock/{symbol}",
    response_model=CommunityPostListResponse,
    summary="Get all posts related to a specific stock symbol",
)
async def get_stock_posts(
    symbol: str,
    q: Optional[str] = Query(None, description="Optional search query within stock posts"),
    cursor: Optional[str] = Query(None, description="Pagination cursor"),
    limit: int = Query(20, ge=1, le=50, description="Items per page"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        posts, next_cursor, has_more = await service.get_feed(
            current_user_id=user.id,
            stock_symbol=symbol,
            search_query=q,
            cursor=cursor,
            limit=limit,
        )

        post_ids = [p.id for p in posts]
        liked_set, bookmarked_set = await service.batch_fetch_post_interactions(post_ids, user.id)

        post_responses = [
            _build_post_response(
                p,
                liked_by_me=p.id in liked_set,
                bookmarked_by_me=p.id in bookmarked_set,
            )
            for p in posts
        ]

        return CommunityPostListResponse(
            posts=post_responses,
            cursor=next_cursor or "",
            next_cursor=next_cursor or "",
            has_more=has_more,
        )
    except Exception:
        log.exception("Get stock posts failed for symbol %s", symbol)
        raise ServiceUnavailableError(f"Failed to get posts for stock {symbol}")


@router.get(
    "/community/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Get a single post",
)
async def get_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        is_admin = getattr(user, "is_admin", False)
        post_data = await service.get_post_with_details(
            post_id,
            current_user_id=user.id,
            include_hidden=is_admin,
        )
        post = post_data["post"]

        if post.status != PostStatus.PUBLISHED.value and post.author_id != user.id and not is_admin:
            raise NotFoundError("Post not found")

        return _build_post_response(
            post,
            liked_by_me=post_data["liked_by_me"],
            bookmarked_by_me=post_data["bookmarked_by_me"],
        )
    except NotFoundError:
        raise
    except Exception:
        log.exception("Get post failed")
        raise ServiceUnavailableError("Failed to get post")


@router.patch(
    "/community/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Update own post",
)
@router.put(
    "/community/posts/{post_id}",
    response_model=CommunityPostResponse,
    summary="Update own post (PUT alias)",
)
async def update_post(
    post_id: str,
    data: CommunityPostUpdate,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        post = await service.update_post(post_id, user.id, data.content)
        post_data = await service.get_post_with_details(post.id, current_user_id=user.id)
        return _build_post_response(
            post_data["post"],
            liked_by_me=post_data["liked_by_me"],
            bookmarked_by_me=post_data["bookmarked_by_me"],
        )
    except (NotFoundError, ForbiddenError, ConflictError, ValidationFailedError):
        raise
    except Exception:
        log.exception("Update post failed")
        raise ServiceUnavailableError("Failed to update post")


@router.delete(
    "/community/posts/{post_id}",
    status_code=204,
    summary="Delete own post",
)
async def delete_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.delete_post(post_id, user.id)
    except (NotFoundError, ForbiddenError):
        raise
    except Exception:
        log.exception("Delete post failed")
        raise ServiceUnavailableError("Failed to delete post")


@router.post(
    "/community/posts/{post_id}/like",
    status_code=204,
    summary="Like a post",
)
async def like_post(
    post_id: str,
    idempotency_key: Optional[str] = Header(None, alias="Idempotency-Key"),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.like_post(post_id, user.id)
    except (NotFoundError, ConflictError):
        raise
    except Exception:
        log.exception("Like post failed")
        raise ServiceUnavailableError("Failed to like post")


@router.delete(
    "/community/posts/{post_id}/like",
    status_code=204,
    summary="Unlike a post",
)
async def unlike_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.unlike_post(post_id, user.id)
    except NotFoundError:
        raise
    except Exception:
        log.exception("Unlike post failed")
        raise ServiceUnavailableError("Failed to unlike post")


@router.post(
    "/community/posts/{post_id}/bookmark",
    status_code=204,
    summary="Bookmark a post",
)
async def bookmark_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.bookmark_post(post_id, user.id)
    except (NotFoundError, ConflictError):
        raise
    except Exception:
        log.exception("Bookmark post failed")
        raise ServiceUnavailableError("Failed to bookmark post")


@router.delete(
    "/community/posts/{post_id}/bookmark",
    status_code=204,
    summary="Unbookmark a post",
)
async def unbookmark_post(
    post_id: str,
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        await service.unbookmark_post(post_id, user.id)
    except NotFoundError:
        raise
    except Exception:
        log.exception("Unbookmark post failed")
        raise ServiceUnavailableError("Failed to unbookmark post")


@router.post(
    "/community/posts/{post_id}/report",
    status_code=201,
    summary="Report a post",
)
async def report_post(
    post_id: str,
    reason: str = Form(...),
    user: User = Depends(get_current_user),
    service: CommunityService = Depends(_get_service),
):
    try:
        from app.schemas.community import ReportReason
        await service.create_report(
            reporter_id=user.id,
            reason=ReportReason(reason),
            post_id=post_id,
        )

        from app.tasks.community_tasks import process_post_report_threshold
        from app.core.task_runner import dispatch_task
        dispatch_task(process_post_report_threshold, post_id)
    except (NotFoundError, ConflictError, ValidationFailedError):
        raise
    except ValueError as e:
        raise ValidationFailedError(f"Invalid report reason: {e}")
    except Exception:
        log.exception("Report post failed")
        raise ServiceUnavailableError("Failed to report post")
