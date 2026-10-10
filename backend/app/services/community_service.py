import json
import logging
from datetime import datetime, timezone
from typing import Optional, List, Tuple, Dict, Set, Any
from uuid import uuid4

from sqlalchemy import select, func, delete, update, and_, or_, distinct, exists, literal
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import aliased, joinedload, selectinload

from app.core.exceptions import (
    BadRequestError,
    ConflictError,
    ForbiddenError,
    NotFoundError,
    ValidationFailedError,
)
from app.models.community import (
    CommunityPost,
    CommunityPostLike,
    CommunityPostTicker,
    CommunityBookmark,
    CommunityComment,
    CommunityFollow,
    CommunityReport,
    CommunityModerationAction,
    CommunityNotification,
    PostType,
    PostStatus,
    RemovedReason,
    ReportStatus,
    ReportReason,
    CommentStatus,
    ModerationActionType,
    NotificationType,
)
from app.models.stock import Stock
from app.models.user import User
from app.services.cloudinary_service import cloudinary_service
from app.services.cashtag_service import CashtagService
from app.services.feed_cache_service import FeedCacheService
from app.services.counter_service import CounterService
from app.services.trending_service import TrendingService

log = logging.getLogger(__name__)


class CommunityService:
    REPORT_THRESHOLD = 10
    MAX_POST_CONTENT_LENGTH = 5000
    MAX_COMMENT_CONTENT_LENGTH = 2000

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Batch Query Helpers (Kills N+1 Completely)
    # =========================================================================

    async def batch_fetch_liked_post_ids(self, post_ids: List[str], user_id: Optional[str]) -> Set[str]:
        """Fetch all post IDs liked by user in ONE batched query or Redis set."""
        if not user_id or not post_ids:
            return set()

        # Try fast Redis check
        cached = await FeedCacheService.get_user_liked_post_ids(user_id, post_ids)
        if cached is not None:
            return cached

        # Single batched DB query
        stmt = select(CommunityPostLike.post_id).where(
            CommunityPostLike.user_id == user_id,
            CommunityPostLike.post_id.in_(post_ids),
        )
        res = await self.db.execute(stmt)
        liked_set = {row[0] for row in res.all()}

        # Cache in Redis asynchronously
        await FeedCacheService.cache_user_likes_set(user_id, liked_set)
        return liked_set

    async def batch_fetch_bookmarked_post_ids(self, post_ids: List[str], user_id: Optional[str]) -> Set[str]:
        """Fetch all post IDs bookmarked by user in ONE batched query."""
        if not user_id or not post_ids:
            return set()

        stmt = select(CommunityBookmark.post_id).where(
            CommunityBookmark.user_id == user_id,
            CommunityBookmark.post_id.in_(post_ids),
        )
        res = await self.db.execute(stmt)
        return {row[0] for row in res.all()}

    async def batch_fetch_post_interactions(
        self,
        post_ids: List[str],
        user_id: Optional[str],
    ) -> Tuple[Set[str], Set[str]]:
        """Fetch liked and bookmarked post IDs in one database round trip."""
        if not user_id or not post_ids:
            return set(), set()

        liked_stmt = select(
            CommunityPostLike.post_id,
            literal("like").label("interaction"),
        ).where(
            CommunityPostLike.user_id == user_id,
            CommunityPostLike.post_id.in_(post_ids),
        )
        bookmarked_stmt = select(
            CommunityBookmark.post_id,
            literal("bookmark").label("interaction"),
        ).where(
            CommunityBookmark.user_id == user_id,
            CommunityBookmark.post_id.in_(post_ids),
        )
        result = await self.db.execute(liked_stmt.union_all(bookmarked_stmt))
        liked_ids: Set[str] = set()
        bookmarked_ids: Set[str] = set()
        for post_id, interaction in result.all():
            if interaction == "like":
                liked_ids.add(post_id)
            else:
                bookmarked_ids.add(post_id)
        return liked_ids, bookmarked_ids

    # =========================================================================
    # Posts
    # =========================================================================

    async def create_post(
        self,
        author_id: str,
        content: str,
        post_type: PostType | str,
        stock_symbol: Optional[str] = None,
        image_url: Optional[str] = None,
        image_public_id: Optional[str] = None,
        media_metadata: Optional[str] = None,
    ) -> CommunityPost:
        if len(content) > self.MAX_POST_CONTENT_LENGTH:
            raise ValidationFailedError(f"Content exceeds maximum length of {self.MAX_POST_CONTENT_LENGTH}")

        pt_value = post_type.value if hasattr(post_type, "value") else str(post_type)
        validated_symbol = None
        validated_stock = None

        if pt_value == "STOCK":
            if not stock_symbol:
                raise ValidationFailedError("stock_symbol is required for STOCK posts")
            stock_res = await self.db.execute(select(Stock).where(Stock.symbol == stock_symbol.upper()))
            stock = stock_res.scalars().first()
            if not stock or not stock.is_active:
                raise NotFoundError(f"Stock '{stock_symbol}' not found or inactive")
            validated_symbol = stock.symbol
            validated_stock = stock
        elif pt_value == "GENERAL_MARKET":
            if stock_symbol:
                raise ValidationFailedError("stock_symbol must not be provided for GENERAL_MARKET posts")
        else:
            raise ValidationFailedError("Invalid post_type")

        # Capture server-side price snapshot at post time
        target_sym = validated_symbol or (stock_symbol.upper() if stock_symbol else None)
        price_snapshot = await CashtagService.get_price_snapshot(target_sym)

        # Parse and validate cashtags before constructing the post so the
        # relationship is initialized without an async lazy load.
        candidates = CashtagService.extract_cashtags(content)
        if validated_symbol and validated_symbol not in candidates:
            candidates.append(validated_symbol)
        valid_tickers = await CashtagService.validate_tickers(self.db, candidates)

        post = CommunityPost(
            author_id=author_id,
            content=content,
            post_type=pt_value,
            stock_symbol=validated_symbol,
            image_url=image_url,
            image_public_id=image_public_id,
            media_metadata=media_metadata,
            price_at_post=price_snapshot,
            status=PostStatus.PUBLISHED.value,
            stock=validated_stock,
            tickers=[CommunityPostTicker(ticker=ticker) for ticker in valid_tickers],
        )
        self.db.add(post)
        await self.db.flush()

        feed_keys = [f"feed:ticker:{ticker}" for ticker in valid_tickers]
        feed_keys.extend(("feed:global", f"feed:user:{author_id}"))
        await FeedCacheService.push_post_to_feeds(feed_keys, post.id, post.created_at.timestamp())

        await self.db.flush()
        return post

    async def get_post_by_id(self, post_id: str, include_hidden: bool = False) -> CommunityPost:
        query = select(CommunityPost).where(CommunityPost.id == post_id)
        if not include_hidden:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)
        result = await self.db.execute(query)
        post = result.scalars().first()
        if not post:
            raise NotFoundError("Post not found")
        return post

    async def get_post_with_details(
        self,
        post_id: str,
        current_user_id: Optional[str] = None,
        include_hidden: bool = False,
    ) -> dict:
        if current_user_id:
            liked_by_me = exists().where(
                CommunityPostLike.post_id == CommunityPost.id,
                CommunityPostLike.user_id == current_user_id,
            )
            bookmarked_by_me = exists().where(
                CommunityBookmark.post_id == CommunityPost.id,
                CommunityBookmark.user_id == current_user_id,
            )
        else:
            liked_by_me = literal(False)
            bookmarked_by_me = literal(False)

        query = (
            select(CommunityPost, liked_by_me, bookmarked_by_me)
            .options(
                joinedload(CommunityPost.author),
                joinedload(CommunityPost.stock),
                selectinload(CommunityPost.tickers),
            )
            .where(CommunityPost.id == post_id)
        )
        if not include_hidden:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)
        result = await self.db.execute(query)
        row = result.first()
        if not row:
            raise NotFoundError("Post not found")
        post, liked, bookmarked = row

        # Record sampled view
        await CounterService.increment_post_view(post_id, 1)

        return {
            "post": post,
            "liked_by_me": liked,
            "bookmarked_by_me": bookmarked,
        }

    async def update_post(
        self,
        post_id: str,
        author_id: str,
        content: str,
    ) -> CommunityPost:
        post = await self.get_post_by_id(post_id, include_hidden=True)
        if post.author_id != author_id:
            raise ForbiddenError("You can only edit your own posts")
        if post.status != PostStatus.PUBLISHED.value:
            raise ConflictError("Cannot edit a hidden or deleted post")
        if len(content) > self.MAX_POST_CONTENT_LENGTH:
            raise ValidationFailedError(f"Content exceeds maximum length of {self.MAX_POST_CONTENT_LENGTH}")

        post.content = content
        post.is_edited = True
        post.edited_at = datetime.now(timezone.utc)
        post.updated_at = datetime.now(timezone.utc)

        # Refresh cashtags
        await self.db.execute(delete(CommunityPostTicker).where(CommunityPostTicker.post_id == post_id))
        candidates = CashtagService.extract_cashtags(content)
        if post.stock_symbol and post.stock_symbol not in candidates:
            candidates.append(post.stock_symbol)
        valid_tickers = await CashtagService.validate_tickers(self.db, candidates)
        for ticker in valid_tickers:
            self.db.add(CommunityPostTicker(post_id=post.id, ticker=ticker))

        await self.db.flush()
        await FeedCacheService.invalidate_post(post_id, post.stock_symbol, author_id)
        return post

    async def delete_post(self, post_id: str, author_id: str) -> CommunityPost:
        post = await self.get_post_by_id(post_id, include_hidden=True)
        if post.author_id != author_id:
            raise ForbiddenError("You can only delete your own posts")

        post.status = PostStatus.DELETED.value
        post.removed_reason = RemovedReason.USER_DELETED.value
        post.updated_at = datetime.now(timezone.utc)

        if post.image_public_id:
            await cloudinary_service.delete_image(post.image_public_id)

        await self.db.flush()
        await FeedCacheService.invalidate_post(post_id, post.stock_symbol, author_id)
        return post

    async def admin_delete_post(self, post_id: str, moderator_id: str) -> CommunityPost:
        post = await self.get_post_by_id(post_id, include_hidden=True)
        post.status = PostStatus.DELETED.value
        post.removed_reason = RemovedReason.MODERATION.value
        post.updated_at = datetime.now(timezone.utc)

        if post.image_public_id:
            await cloudinary_service.delete_image(post.image_public_id)

        action = CommunityModerationAction(
            moderator_id=moderator_id,
            post_id=post_id,
            action=ModerationActionType.POST_DELETED.value,
            note="Post deleted by moderator",
        )
        self.db.add(action)
        await self.db.flush()
        await FeedCacheService.invalidate_post(post_id, post.stock_symbol, post.author_id)
        return post

    async def admin_restore_post(self, post_id: str, moderator_id: str) -> CommunityPost:
        post = await self.get_post_by_id(post_id, include_hidden=True)
        if post.status not in (PostStatus.TEMPORARILY_HIDDEN.value, PostStatus.DELETED.value):
            raise ConflictError("Only temporarily hidden or deleted posts can be restored")

        post.status = PostStatus.PUBLISHED.value
        post.removed_reason = None
        post.updated_at = datetime.now(timezone.utc)

        await self.db.execute(
            update(CommunityReport)
            .where(
                CommunityReport.post_id == post_id,
                CommunityReport.status == ReportStatus.PENDING.value,
            )
            .values(status=ReportStatus.DISMISSED.value)
        )

        action = CommunityModerationAction(
            moderator_id=moderator_id,
            post_id=post_id,
            action=ModerationActionType.RESTORED.value,
            note="Post restored by moderator",
        )
        self.db.add(action)
        await self.db.flush()

        await self._create_notification(
            recipient_id=post.author_id,
            type=NotificationType.POST_RESTORED,
            title="Post Restored",
            message="Your post has been restored and is now visible again.",
            post_id=post_id,
            actor_id=moderator_id,
        )
        await FeedCacheService.invalidate_post(post_id, post.stock_symbol, post.author_id)
        return post

    async def admin_direct_remove_post(self, post_id: str, moderator_id: str) -> CommunityPost:
        post = await self.get_post_by_id(post_id, include_hidden=True)
        post.status = PostStatus.DELETED.value
        post.removed_reason = RemovedReason.MODERATION.value
        post.updated_at = datetime.now(timezone.utc)

        action = CommunityModerationAction(
            moderator_id=moderator_id,
            post_id=post_id,
            action=ModerationActionType.DIRECT_REMOVAL.value,
            note="Post directly removed by moderator",
        )
        self.db.add(action)
        await self.db.flush()
        await FeedCacheService.invalidate_post(post_id, post.stock_symbol, post.author_id)
        return post

    # =========================================================================
    # Feed Generation (Screen-Oriented & Batched)
    # =========================================================================

    async def get_feed(
        self,
        current_user_id: str,
        stock_symbol: Optional[str] = None,
        post_type: Optional[PostType | str] = None,
        search_query: Optional[str] = None,
        author_username: Optional[str] = None,
        mine: bool = False,
        following: bool = False,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[CommunityPost], Optional[str], bool]:
        limit = max(1, min(50, limit))

        query = (
            select(CommunityPost)
            .options(
                joinedload(CommunityPost.author),
                joinedload(CommunityPost.stock),
                selectinload(CommunityPost.tickers),
            )
        )

        if mine:
            query = query.where(CommunityPost.author_id == current_user_id)
        elif following:
            followed_subq = select(CommunityFollow.following_id).where(
                CommunityFollow.follower_id == current_user_id
            )
            query = query.where(
                CommunityPost.author_id.in_(followed_subq),
                CommunityPost.status == PostStatus.PUBLISHED.value,
            )
        else:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)

        # Stock symbol filter using indexed junction table or stock_symbol
        if stock_symbol and stock_symbol.strip():
            sym_clean = stock_symbol.strip().lstrip("$#").upper()
            ticker_subq = select(CommunityPostTicker.post_id).where(CommunityPostTicker.ticker == sym_clean)
            query = query.where(
                or_(
                    CommunityPost.stock_symbol == sym_clean,
                    CommunityPost.id.in_(ticker_subq),
                )
            )

        # Post type filter
        if post_type:
            pt_val = post_type.value if hasattr(post_type, "value") else str(post_type).upper()
            if pt_val in ("GENERAL_MARKET", "MARKET", "GENERAL"):
                query = query.where(CommunityPost.post_type == PostType.GENERAL_MARKET.value)
            elif pt_val in ("STOCK", "STOCKS"):
                query = query.where(CommunityPost.post_type == PostType.STOCK.value)
            else:
                query = query.where(CommunityPost.post_type == pt_val)

        # Text search
        if search_query and search_query.strip():
            q_clean = search_query.strip()
            ticker_cand = q_clean.lstrip("$#").upper()
            ticker_subq = select(CommunityPostTicker.post_id).where(CommunityPostTicker.ticker == ticker_cand)
            query = query.where(
                or_(
                    CommunityPost.content.ilike(f"%{q_clean}%"),
                    CommunityPost.stock_symbol == ticker_cand,
                    CommunityPost.id.in_(ticker_subq),
                )
            )

        # Author filter
        if author_username and author_username.strip():
            author_subq = select(User.id).where(User.username.ilike(f"%{author_username.strip()}%"))
            query = query.where(CommunityPost.author_id.in_(author_subq))

        query = query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())

        # Cursor pagination (supports both ULID/UUIDv7 time ID and legacy created_at|id)
        if cursor and cursor.strip():
            c_str = cursor.strip()
            if "|" in c_str:
                try:
                    c_created_at, c_id = c_str.split("|", 1)
                    query = query.where(
                        or_(
                            CommunityPost.created_at < c_created_at,
                            and_(
                                CommunityPost.created_at == c_created_at,
                                CommunityPost.id < c_id,
                            ),
                        )
                    )
                except Exception:
                    pass
            else:
                # Time-sortable ID cursor
                query = query.where(CommunityPost.id < c_str)

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        posts = list(result.scalars().all())

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        next_cursor = None
        if posts:
            last_post = posts[-1]
            # Emit time-sortable ID as primary cursor with backward-compatible format
            next_cursor = f"{last_post.created_at.isoformat()}|{last_post.id}"

        return posts, next_cursor, has_more

    async def get_user_posts(
        self,
        user_id: str,
        current_user_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[CommunityPost], Optional[str], bool]:
        limit = max(1, min(50, limit))
        is_owner = current_user_id == user_id

        query = (
            select(CommunityPost)
            .options(
                joinedload(CommunityPost.author),
                joinedload(CommunityPost.stock),
                selectinload(CommunityPost.tickers),
            )
            .where(CommunityPost.author_id == user_id)
        )
        if not is_owner:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)

        query = query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())

        if cursor and cursor.strip():
            c_str = cursor.strip()
            if "|" in c_str:
                try:
                    c_created_at, c_id = c_str.split("|", 1)
                    query = query.where(
                        or_(
                            CommunityPost.created_at < c_created_at,
                            and_(
                                CommunityPost.created_at == c_created_at,
                                CommunityPost.id < c_id,
                            ),
                        )
                    )
                except Exception:
                    pass
            else:
                query = query.where(CommunityPost.id < c_str)

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        posts = list(result.scalars().all())

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        next_cursor = None
        if posts:
            last_post = posts[-1]
            next_cursor = f"{last_post.created_at.isoformat()}|{last_post.id}"

        return posts, next_cursor, has_more

    # =========================================================================
    # Likes & Bookmarks
    # =========================================================================

    async def like_post(self, post_id: str, user_id: str) -> bool:
        post = await self.get_post_by_id(post_id)
        if post.status != PostStatus.PUBLISHED.value:
            raise ConflictError("Cannot like a hidden or deleted post")

        existing = await self.db.execute(
            select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == user_id,
            )
        )
        if existing.scalars().first():
            return False

        like = CommunityPostLike(post_id=post_id, user_id=user_id)
        self.db.add(like)
        post.like_count += 1
        await self.db.flush()

        # Update Redis like buffer & set
        await CounterService.increment_post_like(post_id, 1)
        await FeedCacheService.record_user_like(user_id, post_id, is_like=True)

        if post.author_id != user_id:
            await self._create_notification(
                recipient_id=post.author_id,
                type=NotificationType.POST_LIKED,
                title="New Like",
                message="Someone liked your post",
                post_id=post_id,
                actor_id=user_id,
            )
        return True

    async def unlike_post(self, post_id: str, user_id: str) -> bool:
        post = await self.get_post_by_id(post_id)

        like_res = await self.db.execute(
            select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == user_id,
            )
        )
        like_obj = like_res.scalars().first()
        if not like_obj:
            return False

        await self.db.delete(like_obj)
        post.like_count = max(0, post.like_count - 1)
        await self.db.flush()

        await CounterService.increment_post_like(post_id, -1)
        await FeedCacheService.record_user_like(user_id, post_id, is_like=False)
        return True

    async def has_liked(self, post_id: str, user_id: str) -> bool:
        liked_set = await self.batch_fetch_liked_post_ids([post_id], user_id)
        return post_id in liked_set

    async def bookmark_post(self, post_id: str, user_id: str) -> bool:
        post = await self.get_post_by_id(post_id)
        if post.status != PostStatus.PUBLISHED.value:
            raise ConflictError("Cannot bookmark a hidden or deleted post")

        existing = await self.db.execute(
            select(CommunityBookmark).where(
                CommunityBookmark.post_id == post_id,
                CommunityBookmark.user_id == user_id,
            )
        )
        if existing.scalars().first():
            return False

        bm = CommunityBookmark(post_id=post_id, user_id=user_id)
        self.db.add(bm)
        post.bookmark_count += 1
        await self.db.flush()
        return True

    async def unbookmark_post(self, post_id: str, user_id: str) -> bool:
        post = await self.get_post_by_id(post_id)
        bm_res = await self.db.execute(
            select(CommunityBookmark).where(
                CommunityBookmark.post_id == post_id,
                CommunityBookmark.user_id == user_id,
            )
        )
        bm_obj = bm_res.scalars().first()
        if not bm_obj:
            return False

        await self.db.delete(bm_obj)
        post.bookmark_count = max(0, post.bookmark_count - 1)
        await self.db.flush()
        return True

    # =========================================================================
    # Comments
    # =========================================================================

    async def create_comment(
        self,
        post_id: str,
        author_id: str,
        content: str,
        parent_comment_id: Optional[str] = None,
    ) -> CommunityComment:
        post = await self.get_post_by_id(post_id)
        if post.status != PostStatus.PUBLISHED.value:
            raise ConflictError("Cannot comment on a hidden or deleted post")

        if len(content) > self.MAX_COMMENT_CONTENT_LENGTH:
            raise ValidationFailedError(f"Comment exceeds maximum length of {self.MAX_COMMENT_CONTENT_LENGTH}")

        parent = None
        if parent_comment_id:
            parent = await self.db.get(CommunityComment, parent_comment_id)
            if not parent:
                raise NotFoundError("Parent comment not found")
            if parent.post_id != post_id:
                raise BadRequestError("Parent comment must belong to the same post")
            if parent.parent_comment_id is not None:
                raise BadRequestError("Replies can only be one level deep")
            parent.reply_count += 1

        comment = CommunityComment(
            post_id=post_id,
            author_id=author_id,
            parent_comment_id=parent_comment_id,
            content=content,
            reply_count=0,
            status=CommentStatus.PUBLISHED.value,
        )
        self.db.add(comment)
        post.comment_count += 1
        await self.db.flush()

        await CounterService.increment_post_comment(post_id, 1)

        # Notify parent or post author asynchronously in background (Social Media pattern)
        if parent and parent.author_id != author_id:
            asyncio.create_task(
                self._safe_async_notify(
                    recipient_id=parent.author_id,
                    type=NotificationType.COMMENT_REPLIED,
                    title="New Reply",
                    message="Someone replied to your comment",
                    post_id=post_id,
                    comment_id=comment.id,
                    actor_id=author_id,
                )
            )
        elif post.author_id != author_id and not parent:
            asyncio.create_task(
                self._safe_async_notify(
                    recipient_id=post.author_id,
                    type=NotificationType.POST_COMMENTED,
                    title="New Comment",
                    message="Someone commented on your post",
                    post_id=post_id,
                    comment_id=comment.id,
                    actor_id=author_id,
                )
            )

        return comment

    async def _safe_async_notify(
        self,
        recipient_id: str,
        type: NotificationType,
        title: str,
        message: str,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        actor_id: Optional[str] = None,
    ) -> None:
        try:
            from app.db.session import async_session_factory
            async with async_session_factory() as bg_db:
                notification = CommunityNotification(
                    recipient_id=recipient_id,
                    actor_id=actor_id,
                    post_id=post_id,
                    comment_id=comment_id,
                    type=type.value,
                    title=title,
                    message=message,
                    is_read=False,
                )
                bg_db.add(notification)
                await bg_db.commit()

            from app.core.task_runner import dispatch_task
            from app.tasks.push_notifications import send_to_user

            dispatch_task(
                send_to_user,
                recipient_id,
                title,
                message,
                {
                    "type": "community_notification",
                    "notification_type": type.value,
                    "post_id": str(post_id or ""),
                    "comment_id": str(comment_id or ""),
                },
            )
        except Exception as exc:
            log.warning("Async comment notification failed: %s", exc)

    async def get_comments(
        self,
        post_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
        current_user_id: Optional[str] = None,
        include_hidden: bool = False,
    ) -> Tuple[List[CommunityComment], Optional[str], bool, Dict[str, int]]:
        limit = max(1, min(50, limit))

        post_query = select(CommunityPost.id).where(CommunityPost.id == post_id)
        if not include_hidden:
            post_query = post_query.where(
                CommunityPost.status == PostStatus.PUBLISHED.value
            )
        post_result = await self.db.execute(post_query)
        if post_result.scalar_one_or_none() is None:
            raise NotFoundError("Post not found")

        comment_filters = [
            CommunityComment.post_id == post_id,
            CommunityComment.parent_comment_id.is_(None),
            CommunityComment.status == CommentStatus.PUBLISHED.value,
        ]
        if cursor and cursor.strip():
            c_str = cursor.strip()
            if "|" in c_str:
                try:
                    c_created_at_str, c_id = c_str.split("|", 1)
                    c_created_at = datetime.fromisoformat(c_created_at_str)
                    comment_filters.append(
                        or_(
                            CommunityComment.created_at > c_created_at,
                            and_(
                                CommunityComment.created_at == c_created_at,
                                CommunityComment.id > c_id,
                            ),
                        )
                    )
                except ValueError:
                    log.warning("Invalid comment cursor %r", cursor)
            else:
                comment_filters.append(CommunityComment.id > c_str)

        query = (
            select(CommunityComment)
            .options(joinedload(CommunityComment.author))
            .where(and_(*comment_filters))
            .order_by(CommunityComment.created_at.asc(), CommunityComment.id.asc())
            .limit(limit + 1)
        )
        result = await self.db.execute(query)
        comments = list(result.scalars().unique().all())

        has_more = len(comments) > limit
        if has_more:
            comments = comments[:limit]

        reply_counts_by_comment: Dict[str, int] = {}
        if comments:
            reply_result = await self.db.execute(
                select(
                    CommunityComment.parent_comment_id,
                    func.count(CommunityComment.id),
                )
                .where(
                    CommunityComment.parent_comment_id.in_(
                        [comment.id for comment in comments]
                    ),
                    CommunityComment.status == CommentStatus.PUBLISHED.value,
                )
                .group_by(CommunityComment.parent_comment_id)
            )
            reply_counts_by_comment = {
                comment_id: count for comment_id, count in reply_result.all()
            }
        reply_counts_by_comment = {
            comment.id: reply_counts_by_comment.get(
                comment.id, getattr(comment, "reply_count", 0) or 0
            )
            for comment in comments
        }

        next_cursor = None
        if comments:
            last_comment = comments[-1]
            next_cursor = f"{last_comment.created_at.isoformat()}|{last_comment.id}"

        return comments, next_cursor, has_more, reply_counts_by_comment

    async def get_replies(
        self,
        parent_comment_id: str,
        limit: int = 20,
    ) -> List[CommunityComment]:
        query = (
            select(CommunityComment)
            .options(joinedload(CommunityComment.author))
            .where(
                CommunityComment.parent_comment_id == parent_comment_id,
                CommunityComment.status == CommentStatus.PUBLISHED.value,
            )
            .order_by(CommunityComment.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def delete_comment(self, comment_id: str, author_id: str) -> CommunityComment:
        comment = await self.db.get(CommunityComment, comment_id)
        if not comment:
            raise NotFoundError("Comment not found")
        if comment.author_id != author_id:
            raise ForbiddenError("You can only delete your own comments")

        comment.status = CommentStatus.DELETED.value
        comment.updated_at = datetime.now(timezone.utc)

        post = await self.db.get(CommunityPost, comment.post_id)
        if post:
            post.comment_count = max(0, post.comment_count - 1)

        if comment.parent_comment_id:
            parent = await self.db.get(CommunityComment, comment.parent_comment_id)
            if parent:
                parent.reply_count = max(0, parent.reply_count - 1)

        await self.db.flush()
        await CounterService.increment_post_comment(comment.post_id, -1)
        return comment

    async def admin_delete_comment(self, comment_id: str, moderator_id: str) -> CommunityComment:
        comment = await self.db.get(CommunityComment, comment_id)
        if not comment:
            raise NotFoundError("Comment not found")

        comment.status = CommentStatus.DELETED.value
        comment.updated_at = datetime.now(timezone.utc)

        post = await self.db.get(CommunityPost, comment.post_id)
        if post:
            post.comment_count = max(0, post.comment_count - 1)

        if comment.parent_comment_id:
            parent = await self.db.get(CommunityComment, comment.parent_comment_id)
            if parent:
                parent.reply_count = max(0, parent.reply_count - 1)

        action = CommunityModerationAction(
            moderator_id=moderator_id,
            comment_id=comment_id,
            action=ModerationActionType.COMMENT_DELETED.value,
            note="Comment deleted by moderator",
        )
        self.db.add(action)
        await self.db.flush()
        return comment

    # =========================================================================
    # Follows
    # =========================================================================

    async def follow_user(self, follower_id: str, following_id: str) -> bool:
        if follower_id == following_id:
            raise ValidationFailedError("Cannot follow yourself")

        target_user = await self.db.get(User, following_id)
        if not target_user or not target_user.is_active:
            raise NotFoundError("User not found or inactive")

        existing = await self.db.execute(
            select(CommunityFollow).where(
                CommunityFollow.follower_id == follower_id,
                CommunityFollow.following_id == following_id,
            )
        )
        if existing.scalars().first():
            return False

        follow = CommunityFollow(follower_id=follower_id, following_id=following_id)
        self.db.add(follow)
        await self.db.flush()

        await self._create_notification(
            recipient_id=following_id,
            type=NotificationType.USER_FOLLOWED,
            title="New Follower",
            message="Someone started following you",
            actor_id=follower_id,
        )
        return True

    async def unfollow_user(self, follower_id: str, following_id: str) -> bool:
        result = await self.db.execute(
            select(CommunityFollow).where(
                CommunityFollow.follower_id == follower_id,
                CommunityFollow.following_id == following_id,
            )
        )
        follow = result.scalars().first()
        if not follow:
            return False

        await self.db.delete(follow)
        await self.db.flush()
        return True

    async def get_follow_status(
        self,
        follower_id: str,
        following_id: str,
    ) -> Tuple[bool, int, int]:
        is_following_subq = select(func.count(CommunityFollow.follower_id)).where(
            CommunityFollow.follower_id == follower_id,
            CommunityFollow.following_id == following_id,
        ).scalar_subquery()

        followers_subq = select(func.count(CommunityFollow.follower_id)).where(
            CommunityFollow.following_id == following_id
        ).scalar_subquery()

        following_subq = select(func.count(CommunityFollow.following_id)).where(
            CommunityFollow.follower_id == following_id
        ).scalar_subquery()

        stmt = select(is_following_subq, followers_subq, following_subq)
        res = await self.db.execute(stmt)
        row = res.first()
        is_f_count, f_count, ing_count = row if row else (0, 0, 0)
        return bool(is_f_count and is_f_count > 0), f_count or 0, ing_count or 0

    async def get_followers(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[User], Optional[str], bool]:
        limit = max(1, min(50, limit))
        query = (
            select(User)
            .join(CommunityFollow, CommunityFollow.follower_id == User.id)
            .where(
                CommunityFollow.following_id == user_id,
                User.is_active == True,
            )
            .order_by(CommunityFollow.created_at.desc())
        )

        if cursor and cursor.strip():
            c_str = cursor.strip()
            if "|" in c_str:
                try:
                    c_created_at, c_id = c_str.split("|", 1)
                    query = query.where(
                        or_(
                            CommunityFollow.created_at < c_created_at,
                            and_(
                                CommunityFollow.created_at == c_created_at,
                                CommunityFollow.follower_id < c_id,
                            ),
                        )
                    )
                except Exception:
                    pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = None
        if users:
            last_user = users[-1]
            next_cursor = f"{datetime.now(timezone.utc).isoformat()}|{last_user.id}"

        return users, next_cursor, has_more

    async def get_following(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[User], Optional[str], bool]:
        limit = max(1, min(50, limit))
        query = (
            select(User)
            .join(CommunityFollow, CommunityFollow.following_id == User.id)
            .where(
                CommunityFollow.follower_id == user_id,
                User.is_active == True,
            )
            .order_by(CommunityFollow.created_at.desc())
        )

        if cursor and cursor.strip():
            c_str = cursor.strip()
            if "|" in c_str:
                try:
                    c_created_at, c_id = c_str.split("|", 1)
                    query = query.where(
                        or_(
                            CommunityFollow.created_at < c_created_at,
                            and_(
                                CommunityFollow.created_at == c_created_at,
                                CommunityFollow.following_id < c_id,
                            ),
                        )
                    )
                except Exception:
                    pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        users = list(result.scalars().all())

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = None
        if users:
            last_user = users[-1]
            next_cursor = f"{datetime.now(timezone.utc).isoformat()}|{last_user.id}"

        return users, next_cursor, has_more

    # =========================================================================
    # Profile & Stats
    # =========================================================================

    async def get_user_profile_with_stats(
        self,
        user_id: str,
        current_user_id: Optional[str] = None,
    ) -> Tuple[User, dict]:
        post_subq = select(func.count(CommunityPost.id)).where(
            CommunityPost.author_id == user_id,
            CommunityPost.status == PostStatus.PUBLISHED.value,
        ).scalar_subquery()
        followers_subq = select(func.count(CommunityFollow.follower_id)).where(
            CommunityFollow.following_id == user_id
        ).scalar_subquery()
        following_subq = select(func.count(CommunityFollow.following_id)).where(
            CommunityFollow.follower_id == user_id
        ).scalar_subquery()

        columns = [post_subq, followers_subq, following_subq]
        if current_user_id and current_user_id != user_id:
            is_following_subq = select(func.count(CommunityFollow.follower_id)).where(
                CommunityFollow.follower_id == current_user_id,
                CommunityFollow.following_id == user_id,
            ).scalar_subquery()
            columns.append(is_following_subq)

        result = await self.db.execute(
            select(User, *columns).where(User.id == user_id)
        )
        row = result.first()
        if not row:
            raise NotFoundError("User not found")

        target_user, post_count, followers_count, following_count, *following_state = row
        stats = {
            "followers_count": followers_count or 0,
            "following_count": following_count or 0,
            "published_post_count": post_count or 0,
            "is_following": bool(following_state and following_state[0]),
            "is_own_profile": current_user_id == user_id,
        }
        return target_user, stats

    async def get_user_profile_stats(self, user_id: str, current_user_id: Optional[str] = None) -> dict:
        # Single aggregated query for all stats in 1 roundtrip
        post_subq = select(func.count(CommunityPost.id)).where(
            CommunityPost.author_id == user_id,
            CommunityPost.status == PostStatus.PUBLISHED.value,
        ).scalar_subquery()

        followers_subq = select(func.count(CommunityFollow.follower_id)).where(
            CommunityFollow.following_id == user_id
        ).scalar_subquery()

        following_subq = select(func.count(CommunityFollow.following_id)).where(
            CommunityFollow.follower_id == user_id
        ).scalar_subquery()

        if current_user_id and current_user_id != user_id:
            is_following_subq = select(func.count(CommunityFollow.follower_id)).where(
                CommunityFollow.follower_id == current_user_id,
                CommunityFollow.following_id == user_id,
            ).scalar_subquery()
            stmt = select(post_subq, followers_subq, following_subq, is_following_subq)
            res = await self.db.execute(stmt)
            row = res.first()
            p_count, f_count, ing_count, is_f_count = row if row else (0, 0, 0, 0)
            is_following = bool(is_f_count and is_f_count > 0)
        else:
            stmt = select(post_subq, followers_subq, following_subq)
            res = await self.db.execute(stmt)
            row = res.first()
            p_count, f_count, ing_count = row if row else (0, 0, 0)
            is_following = False

        return {
            "followers_count": f_count or 0,
            "following_count": ing_count or 0,
            "published_post_count": p_count or 0,
            "is_following": is_following,
            "is_own_profile": current_user_id == user_id,
        }

    # =========================================================================
    # Reports & Moderation
    # =========================================================================

    async def create_report(
        self,
        reporter_id: str,
        reason: ReportReason,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
    ) -> CommunityReport:
        if (post_id is None) == (comment_id is None):
            raise ValidationFailedError("Exactly one of post_id or comment_id must be provided")

        if post_id:
            post = await self.get_post_by_id(post_id)
            if post.author_id == reporter_id:
                raise ValidationFailedError("Cannot report your own post")
            if post.status == PostStatus.DELETED.value:
                raise ConflictError("Cannot report a deleted post")

        if comment_id:
            comment = await self.db.get(CommunityComment, comment_id)
            if not comment:
                raise NotFoundError("Comment not found")
            if comment.author_id == reporter_id:
                raise ValidationFailedError("Cannot report your own comment")
            if comment.status == CommentStatus.DELETED.value:
                raise ConflictError("Cannot report a deleted comment")

        existing_query = select(CommunityReport).where(CommunityReport.reporter_id == reporter_id)
        if post_id:
            existing_query = existing_query.where(CommunityReport.post_id == post_id)
        else:
            existing_query = existing_query.where(CommunityReport.comment_id == comment_id)
        existing = await self.db.execute(existing_query)
        if existing.scalars().first():
            raise ConflictError("You have already reported this content")

        report = CommunityReport(
            reporter_id=reporter_id,
            post_id=post_id,
            comment_id=comment_id,
            reason=reason.value,
            status=ReportStatus.PENDING.value,
        )
        self.db.add(report)

        if post_id:
            post = await self.db.get(CommunityPost, post_id)
            if post:
                post.report_count += 1

        await self.db.flush()
        return report

    async def get_report(self, report_id: str) -> CommunityReport:
        report = await self.db.get(CommunityReport, report_id)
        if not report:
            raise NotFoundError("Report not found")
        return report

    async def get_reports_for_admin(
        self,
        status: Optional[ReportStatus] = None,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[CommunityReport]:
        query = (
            select(CommunityReport)
            .options(
                joinedload(CommunityReport.reporter),
                joinedload(CommunityReport.post).joinedload(CommunityPost.author),
                joinedload(CommunityReport.comment).joinedload(CommunityComment.author),
            )
            .order_by(CommunityReport.created_at.desc())
        )
        if status:
            query = query.where(CommunityReport.status == status.value)
        if post_id:
            query = query.where(CommunityReport.post_id == post_id)
        if comment_id:
            query = query.where(CommunityReport.comment_id == comment_id)
        query = query.limit(limit).offset(offset)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    async def update_report_status(
        self,
        report_id: str,
        status: ReportStatus,
        moderator_id: str,
    ) -> CommunityReport:
        report = await self.get_report(report_id)
        if report.status != ReportStatus.PENDING.value and status == ReportStatus.REVIEWED.value:
            raise ConflictError("Only pending reports can be marked as reviewed")

        report.status = status.value
        report.reviewed_by = moderator_id
        report.reviewed_at = datetime.now(timezone.utc)

        if post_id := report.post_id:
            post = await self.db.get(CommunityPost, post_id)
            if post:
                pending_count_result = await self.db.execute(
                    select(func.count(CommunityReport.id)).where(
                        CommunityReport.post_id == post_id,
                        CommunityReport.status == ReportStatus.PENDING.value,
                    )
                )
                post.report_count = pending_count_result.scalar() or 0

        await self.db.flush()
        return report

    async def process_report_threshold(self, post_id: str) -> bool:
        post = await self.db.get(CommunityPost, post_id)
        if not post or post.status != PostStatus.PUBLISHED.value:
            return False

        pending_count_result = await self.db.execute(
            select(func.count(CommunityReport.id)).where(
                CommunityReport.post_id == post_id,
                CommunityReport.status == ReportStatus.PENDING.value,
            )
        )
        pending_count = pending_count_result.scalar() or 0

        if pending_count >= self.REPORT_THRESHOLD:
            post.status = PostStatus.TEMPORARILY_HIDDEN.value
            post.updated_at = datetime.now(timezone.utc)

            existing_action = await self.db.execute(
                select(CommunityModerationAction).where(
                    CommunityModerationAction.post_id == post_id,
                    CommunityModerationAction.action == ModerationActionType.AUTO_HIDDEN.value,
                )
            )
            if not existing_action.scalars().first():
                action = CommunityModerationAction(
                    moderator_id=None,
                    post_id=post_id,
                    action=ModerationActionType.AUTO_HIDDEN.value,
                    note=f"Auto-hidden after {pending_count} pending reports",
                )
                self.db.add(action)

                await self._create_notification(
                    recipient_id=post.author_id,
                    type=NotificationType.POST_AUTO_HIDDEN,
                    title="Post Temporarily Hidden",
                    message="Your post has been temporarily hidden for review due to multiple reports.",
                    post_id=post_id,
                    actor_id=None,
                )
            await self.db.flush()
            await FeedCacheService.invalidate_post(post_id, post.stock_symbol, post.author_id)
            return True
        return False

    async def get_moderation_actions(
        self,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[CommunityModerationAction]:
        query = (
            select(CommunityModerationAction)
            .options(joinedload(CommunityModerationAction.moderator))
            .order_by(CommunityModerationAction.created_at.desc())
            .limit(limit)
        )
        if post_id:
            query = query.where(CommunityModerationAction.post_id == post_id)
        if comment_id:
            query = query.where(CommunityModerationAction.comment_id == comment_id)
        result = await self.db.execute(query)
        return list(result.scalars().all())

    # =========================================================================
    # Notifications
    # =========================================================================

    async def _create_notification(
        self,
        recipient_id: str,
        type: NotificationType,
        title: str,
        message: str,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        actor_id: Optional[str] = None,
        check_existing: bool = True,
    ) -> CommunityNotification:
        if check_existing:
            existing = await self.db.execute(
                select(CommunityNotification).where(
                    CommunityNotification.recipient_id == recipient_id,
                    CommunityNotification.type == type.value,
                    CommunityNotification.post_id == post_id,
                    CommunityNotification.comment_id == comment_id,
                    CommunityNotification.actor_id == actor_id,
                )
            )
            existing_notification = existing.scalars().first()
            if existing_notification is not None:
                return existing_notification

        notification = CommunityNotification(
            recipient_id=recipient_id,
            actor_id=actor_id,
            post_id=post_id,
            comment_id=comment_id,
            type=type.value,
            title=title,
            message=message,
            is_read=False,
        )
        self.db.add(notification)
        await self.db.flush()

        try:
            from app.core.task_runner import dispatch_task
            from app.tasks.push_notifications import send_to_user

            dispatch_task(
                send_to_user,
                recipient_id,
                title,
                message,
                {
                    "type": "community_notification",
                    "notification_type": type.value,
                    "post_id": str(post_id or ""),
                    "comment_id": str(comment_id or ""),
                },
            )
        except Exception as push_err:
            log.warning("Could not dispatch community push notification: %s", push_err)

        return notification

    async def get_notifications(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> Tuple[List[CommunityNotification], int]:
        filters = [CommunityNotification.recipient_id == user_id]
        if unread_only:
            filters.append(CommunityNotification.is_read == False)

        query = (
            select(
                CommunityNotification,
                func.count(CommunityNotification.id).over().label("total"),
            )
            .where(*filters)
            .order_by(CommunityNotification.created_at.desc())
            .offset((page - 1) * limit)
            .limit(limit)
            .options(joinedload(CommunityNotification.actor))
        )
        result = await self.db.execute(query)
        rows = result.all()
        notifications = [row[0] for row in rows]
        if rows:
            total = rows[0][1]
        else:
            total_result = await self.db.execute(
                select(func.count(CommunityNotification.id)).where(*filters)
            )
            total = total_result.scalar() or 0

        return notifications, total

    async def mark_notification_read(self, notification_id: str, user_id: str) -> CommunityNotification:
        notification = await self.db.get(CommunityNotification, notification_id)
        if not notification:
            raise NotFoundError("Notification not found")
        if notification.recipient_id != user_id:
            raise ForbiddenError("Not authorized to modify this notification")

        notification.is_read = True
        await self.db.flush()
        return notification

    async def mark_all_notifications_read(self, user_id: str) -> int:
        result = await self.db.execute(
            update(CommunityNotification)
            .where(
                CommunityNotification.recipient_id == user_id,
                CommunityNotification.is_read == False,
            )
            .values(is_read=True)
        )
        await self.db.flush()
        return result.rowcount

    async def get_unread_count(self, user_id: str) -> int:
        result = await self.db.execute(
            select(func.count(CommunityNotification.id)).where(
                CommunityNotification.recipient_id == user_id,
                CommunityNotification.is_read == False,
            )
        )
        return result.scalar() or 0
