from datetime import datetime, timezone
from typing import Optional, List, Tuple
from uuid import uuid4

from sqlalchemy import select, func, delete, update, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

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


class CommunityService:
    REPORT_THRESHOLD = 10
    MAX_POST_CONTENT_LENGTH = 5000
    MAX_COMMENT_CONTENT_LENGTH = 2000

    def __init__(self, db: AsyncSession):
        self.db = db

    # =========================================================================
    # Posts
    # =========================================================================

    async def create_post(
        self,
        author_id: str,
        content: str,
        post_type: PostType,
        stock_symbol: Optional[str] = None,
        image_url: Optional[str] = None,
        image_public_id: Optional[str] = None,
    ) -> CommunityPost:
        if len(content) > self.MAX_POST_CONTENT_LENGTH:
            raise ValidationFailedError(f"Content exceeds maximum length of {self.MAX_POST_CONTENT_LENGTH}")

        pt_value = post_type.value if hasattr(post_type, "value") else str(post_type)
        if pt_value == "STOCK":
            if not stock_symbol:
                raise ValidationFailedError("stock_symbol is required for STOCK posts")
            stock_res = await self.db.execute(select(Stock).where(Stock.symbol == stock_symbol.upper()))
            stock = stock_res.scalars().first()
            if not stock or not stock.is_active:
                raise NotFoundError(f"Stock '{stock_symbol}' not found or inactive")
        elif pt_value == "GENERAL_MARKET":
            if stock_symbol:
                raise ValidationFailedError("stock_symbol must not be provided for GENERAL_MARKET posts")
            stock_symbol = None
        else:
            raise ValidationFailedError("Invalid post_type")

        post = CommunityPost(
            author_id=author_id,
            content=content,
            post_type=post_type.value,
            stock_symbol=stock_symbol,
            image_url=image_url,
            image_public_id=image_public_id,
            status=PostStatus.PUBLISHED.value,
        )
        self.db.add(post)
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
        query = (
            select(CommunityPost)
            .options(
                selectinload(CommunityPost.author),
                selectinload(CommunityPost.stock),
            )
            .where(CommunityPost.id == post_id)
        )
        if not include_hidden:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)
        result = await self.db.execute(query)
        post = result.scalars().first()
        if not post:
            raise NotFoundError("Post not found")

        liked_by_me = False
        if current_user_id:
            like_query = select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == current_user_id,
            )
            like_result = await self.db.execute(like_query)
            liked_by_me = like_result.scalars().first() is not None

        return {
            "post": post,
            "liked_by_me": liked_by_me,
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
        post.updated_at = datetime.now(timezone.utc)
        await self.db.flush()
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
        return post

    # =========================================================================
    # Feed
    # =========================================================================

    async def get_feed(
        self,
        current_user_id: str,
        stock_symbol: Optional[str] = None,
        post_type: Optional[PostType] = None,
        mine: bool = False,
        following: bool = False,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[CommunityPost], Optional[str], bool]:
        if mine:
            query = (
                select(CommunityPost)
                .options(selectinload(CommunityPost.author), selectinload(CommunityPost.stock))
                .where(CommunityPost.author_id == current_user_id)
            )
        elif following:
            followed_subq = select(CommunityFollow.following_id).where(
                CommunityFollow.follower_id == current_user_id
            )
            query = (
                select(CommunityPost)
                .options(selectinload(CommunityPost.author), selectinload(CommunityPost.stock))
                .where(CommunityPost.author_id.in_(followed_subq))
            )
        else:
            query = (
                select(CommunityPost)
                .options(selectinload(CommunityPost.author), selectinload(CommunityPost.stock))
                .where(CommunityPost.status == PostStatus.PUBLISHED.value)
            )

        if stock_symbol:
            query = query.where(CommunityPost.stock_symbol == stock_symbol)
        if post_type:
            query = query.where(CommunityPost.post_type == post_type.value)

        query = query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())

        if cursor:
            try:
                cursor_created_at, cursor_id = cursor.split("|")
                query = query.where(
                    or_(
                        CommunityPost.created_at < cursor_created_at,
                        and_(
                            CommunityPost.created_at == cursor_created_at,
                            CommunityPost.id < cursor_id,
                        ),
                    )
                )
            except ValueError:
                pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        posts = result.scalars().all()

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        next_cursor = None
        if posts:
            last_post = posts[-1]
            next_cursor = f"{last_post.created_at.isoformat()}|{last_post.id}"

        return posts, next_cursor, has_more

    async def get_user_posts(
        self,
        user_id: str,
        current_user_id: Optional[str] = None,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[CommunityPost], Optional[str], bool]:
        is_owner = current_user_id == user_id
        query = (
            select(CommunityPost)
            .options(selectinload(CommunityPost.author), selectinload(CommunityPost.stock))
            .where(CommunityPost.author_id == user_id)
        )
        if not is_owner:
            query = query.where(CommunityPost.status == PostStatus.PUBLISHED.value)

        query = query.order_by(CommunityPost.created_at.desc(), CommunityPost.id.desc())

        if cursor:
            try:
                cursor_created_at, cursor_id = cursor.split("|")
                query = query.where(
                    or_(
                        CommunityPost.created_at < cursor_created_at,
                        and_(
                            CommunityPost.created_at == cursor_created_at,
                            CommunityPost.id < cursor_id,
                        ),
                    )
                )
            except ValueError:
                pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        posts = result.scalars().all()

        has_more = len(posts) > limit
        if has_more:
            posts = posts[:limit]

        next_cursor = None
        if posts:
            last_post = posts[-1]
            next_cursor = f"{last_post.created_at.isoformat()}|{last_post.id}"

        return posts, next_cursor, has_more

    # =========================================================================
    # Likes
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

        if post.author_id != user_id:
            await self._create_notification(
                recipient_id=post.author_id,
                type=NotificationType.POST_LIKED,
                title="New Like",
                message=f"Someone liked your post",
                post_id=post_id,
                actor_id=user_id,
            )
        return True

    async def unlike_post(self, post_id: str, user_id: str) -> bool:
        post = await self.get_post_by_id(post_id)

        like = await self.db.execute(
            select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == user_id,
            )
        )
        like_obj = like.scalars().first()
        if not like_obj:
            return False

        await self.db.delete(like_obj)
        post.like_count = max(0, post.like_count - 1)
        await self.db.flush()
        return True

    async def has_liked(self, post_id: str, user_id: str) -> bool:
        result = await self.db.execute(
            select(CommunityPostLike).where(
                CommunityPostLike.post_id == post_id,
                CommunityPostLike.user_id == user_id,
            )
        )
        return result.scalars().first() is not None

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

        if parent_comment_id:
            parent = await self.db.get(CommunityComment, parent_comment_id)
            if not parent:
                raise NotFoundError("Parent comment not found")
            if parent.post_id != post_id:
                raise BadRequestError("Parent comment must belong to the same post")
            if parent.parent_comment_id is not None:
                raise BadRequestError("Replies can only be one level deep")

        comment = CommunityComment(
            post_id=post_id,
            author_id=author_id,
            parent_comment_id=parent_comment_id,
            content=content,
            status=CommentStatus.PUBLISHED.value,
        )
        self.db.add(comment)

        post.comment_count += 1
        await self.db.flush()

        if post.author_id != author_id:
            if parent_comment_id:
                parent = await self.db.get(CommunityComment, parent_comment_id)
                if parent and parent.author_id != author_id:
                    await self._create_notification(
                        recipient_id=parent.author_id,
                        type=NotificationType.COMMENT_REPLIED,
                        title="New Reply",
                        message=f"Someone replied to your comment",
                        post_id=post_id,
                        comment_id=comment.id,
                        actor_id=author_id,
                    )
            else:
                await self._create_notification(
                    recipient_id=post.author_id,
                    type=NotificationType.POST_COMMENTED,
                    title="New Comment",
                    message=f"Someone commented on your post",
                    post_id=post_id,
                    comment_id=comment.id,
                    actor_id=author_id,
                )
        return comment

    async def get_comments(
        self,
        post_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[CommunityComment], Optional[str], bool]:
        query = (
            select(CommunityComment)
            .options(selectinload(CommunityComment.author))
            .where(
                CommunityComment.post_id == post_id,
                CommunityComment.parent_comment_id.is_(None),
                CommunityComment.status == CommentStatus.PUBLISHED.value,
            )
            .order_by(CommunityComment.created_at.asc(), CommunityComment.id.asc())
        )

        if cursor:
            try:
                cursor_created_at, cursor_id = cursor.split("|")
                query = query.where(
                    or_(
                        CommunityComment.created_at > cursor_created_at,
                        and_(
                            CommunityComment.created_at == cursor_created_at,
                            CommunityComment.id > cursor_id,
                        ),
                    )
                )
            except ValueError:
                pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        comments = result.scalars().all()

        has_more = len(comments) > limit
        if has_more:
            comments = comments[:limit]

        next_cursor = None
        if comments:
            last_comment = comments[-1]
            next_cursor = f"{last_comment.created_at.isoformat()}|{last_comment.id}"

        return comments, next_cursor, has_more

    async def get_replies(
        self,
        parent_comment_id: str,
        limit: int = 10,
    ) -> List[CommunityComment]:
        query = (
            select(CommunityComment)
            .options(selectinload(CommunityComment.author))
            .where(
                CommunityComment.parent_comment_id == parent_comment_id,
                CommunityComment.status == CommentStatus.PUBLISHED.value,
            )
            .order_by(CommunityComment.created_at.asc())
            .limit(limit)
        )
        result = await self.db.execute(query)
        return result.scalars().all()

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

        await self.db.flush()
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
            message=f"Someone started following you",
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
        is_following_result = await self.db.execute(
            select(CommunityFollow).where(
                CommunityFollow.follower_id == follower_id,
                CommunityFollow.following_id == following_id,
            )
        )
        is_following = is_following_result.scalars().first() is not None

        followers_count_result = await self.db.execute(
            select(func.count(CommunityFollow.follower_id)).where(
                CommunityFollow.following_id == following_id
            )
        )
        followers_count = followers_count_result.scalar() or 0

        following_count_result = await self.db.execute(
            select(func.count(CommunityFollow.following_id)).where(
                CommunityFollow.follower_id == following_id
            )
        )
        following_count = following_count_result.scalar() or 0

        return is_following, followers_count, following_count

    async def get_followers(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[User], Optional[str], bool]:
        query = (
            select(User)
            .join(CommunityFollow, CommunityFollow.follower_id == User.id)
            .where(
                CommunityFollow.following_id == user_id,
                User.is_active == True,
            )
            .order_by(CommunityFollow.created_at.desc())
        )

        if cursor:
            try:
                cursor_created_at, cursor_id = cursor.split("|")
                query = query.where(
                    or_(
                        CommunityFollow.created_at < cursor_created_at,
                        and_(
                            CommunityFollow.created_at == cursor_created_at,
                            CommunityFollow.follower_id < cursor_id,
                        ),
                    )
                )
            except ValueError:
                pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        users = result.scalars().all()

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = None
        if users:
            last_user = users[-1]
            next_cursor = f"{last_user.created_at.isoformat()}|{last_user.id}"

        return users, next_cursor, has_more

    async def get_following(
        self,
        user_id: str,
        cursor: Optional[str] = None,
        limit: int = 20,
    ) -> Tuple[List[User], Optional[str], bool]:
        query = (
            select(User)
            .join(CommunityFollow, CommunityFollow.following_id == User.id)
            .where(
                CommunityFollow.follower_id == user_id,
                User.is_active == True,
            )
            .order_by(CommunityFollow.created_at.desc())
        )

        if cursor:
            try:
                cursor_created_at, cursor_id = cursor.split("|")
                query = query.where(
                    or_(
                        CommunityFollow.created_at < cursor_created_at,
                        and_(
                            CommunityFollow.created_at == cursor_created_at,
                            CommunityFollow.following_id < cursor_id,
                        ),
                    )
                )
            except ValueError:
                pass

        query = query.limit(limit + 1)
        result = await self.db.execute(query)
        users = result.scalars().all()

        has_more = len(users) > limit
        if has_more:
            users = users[:limit]

        next_cursor = None
        if users:
            last_user = users[-1]
            next_cursor = f"{last_user.created_at.isoformat()}|{last_user.id}"

        return users, next_cursor, has_more

    # =========================================================================
    # Reports
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
                selectinload(CommunityReport.reporter),
                selectinload(CommunityReport.post).selectinload(CommunityPost.author),
                selectinload(CommunityReport.comment).selectinload(CommunityComment.author),
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
        return result.scalars().all()

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
            return True
        return False

    # =========================================================================
    # Moderation
    # =========================================================================

    async def get_moderation_actions(
        self,
        post_id: Optional[str] = None,
        comment_id: Optional[str] = None,
        limit: int = 50,
    ) -> List[CommunityModerationAction]:
        query = (
            select(CommunityModerationAction)
            .options(selectinload(CommunityModerationAction.moderator))
            .order_by(CommunityModerationAction.created_at.desc())
            .limit(limit)
        )
        if post_id:
            query = query.where(CommunityModerationAction.post_id == post_id)
        if comment_id:
            query = query.where(CommunityModerationAction.comment_id == comment_id)
        result = await self.db.execute(query)
        return result.scalars().all()

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
    ) -> CommunityNotification:
        existing = await self.db.execute(
            select(CommunityNotification).where(
                CommunityNotification.recipient_id == recipient_id,
                CommunityNotification.type == type.value,
                CommunityNotification.post_id == post_id,
                CommunityNotification.comment_id == comment_id,
                CommunityNotification.actor_id == actor_id,
            )
        )
        if existing.scalars().first():
            return existing.scalars().first()

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
        return notification

    async def get_notifications(
        self,
        user_id: str,
        page: int = 1,
        limit: int = 20,
        unread_only: bool = False,
    ) -> Tuple[List[CommunityNotification], int]:
        query = select(CommunityNotification).where(CommunityNotification.recipient_id == user_id)
        if unread_only:
            query = query.where(CommunityNotification.is_read == False)

        total_result = await self.db.execute(
            select(func.count(CommunityNotification.id)).where(query.whereclause)
        )
        total = total_result.scalar() or 0

        query = query.order_by(CommunityNotification.created_at.desc()).offset((page - 1) * limit).limit(limit)
        query = query.options(
            selectinload(CommunityNotification.actor),
            selectinload(CommunityNotification.post),
            selectinload(CommunityNotification.comment),
        )
        result = await self.db.execute(query)
        notifications = result.scalars().all()

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

    # =========================================================================
    # Profile Stats
    # =========================================================================

    async def get_user_profile_stats(self, user_id: str, current_user_id: Optional[str] = None) -> dict:
        post_count_result = await self.db.execute(
            select(func.count(CommunityPost.id)).where(
                CommunityPost.author_id == user_id,
                CommunityPost.status == PostStatus.PUBLISHED.value,
            )
        )
        published_post_count = post_count_result.scalar() or 0

        followers_count_result = await self.db.execute(
            select(func.count(CommunityFollow.follower_id)).where(
                CommunityFollow.following_id == user_id
            )
        )
        followers_count = followers_count_result.scalar() or 0

        following_count_result = await self.db.execute(
            select(func.count(CommunityFollow.following_id)).where(
                CommunityFollow.follower_id == user_id
            )
        )
        following_count = following_count_result.scalar() or 0

        is_following = False
        if current_user_id and current_user_id != user_id:
            follow_result = await self.db.execute(
                select(CommunityFollow).where(
                    CommunityFollow.follower_id == current_user_id,
                    CommunityFollow.following_id == user_id,
                )
            )
            is_following = follow_result.scalars().first() is not None

        return {
            "followers_count": followers_count,
            "following_count": following_count,
            "published_post_count": published_post_count,
            "is_following": is_following,
            "is_own_profile": current_user_id == user_id,
        }