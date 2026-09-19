from datetime import datetime

from sqlalchemy import and_, delete, func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.community import Comment, Post, PostLike, PostStockTag, Report, ShareLink
from app.models.stock import Stock
from app.models.user import User


class CommunityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Stock tags ────────────────────────────────────────────────────────────
    async def resolve_valid_symbols(self, symbols: list[str]) -> set[str]:
        """Return the subset of ``symbols`` that exist in the canonical stocks table."""
        if not symbols:
            return set()
        result = await self.db.execute(
            select(Stock.symbol).where(Stock.symbol.in_(symbols))
        )
        return {row[0] for row in result.all()}

    # ── Posts ─────────────────────────────────────────────────────────────────
    async def create_post(
        self,
        user_id: str,
        content: str,
        sentiment: str | None,
        media_url: str | None,
        symbols: list[str],
    ) -> Post:
        post = Post(
            user_id=user_id,
            content=content,
            sentiment=sentiment,
            media_url=media_url,
        )
        self.db.add(post)
        await self.db.flush()
        for symbol in symbols:
            self.db.add(PostStockTag(post_id=post.id, symbol=symbol))
        await self.db.flush()
        await self.db.refresh(post)
        return post

    async def get_post(self, post_id: str) -> Post | None:
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.id == post_id)
        )
        return result.scalars().first()

    async def get_post_for_update(self, post_id: str) -> Post | None:
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.id == post_id)
            .with_for_update()
        )
        return result.scalars().first()

    async def set_post_status(self, post_id: str, status: str) -> None:
        await self.db.execute(
            update(Post).where(Post.id == post_id).values(status=status)
        )

    async def increment_post_like_count(self, post_id: str, delta: int) -> None:
        await self.db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(like_count=Post.like_count + delta)
        )

    async def increment_post_comment_count(self, post_id: str, delta: int) -> None:
        await self.db.execute(
            update(Post)
            .where(Post.id == post_id)
            .values(comment_count=Post.comment_count + delta)
        )

    async def get_feed(
        self,
        cursor_at: datetime | None = None,
        cursor_id: str | None = None,
        limit: int = 20,
        symbol: str | None = None,
    ) -> list[Post]:
        stmt = (
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.status == "PUBLISHED")
        )
        if symbol:
            stmt = stmt.join(PostStockTag, PostStockTag.post_id == Post.id).where(
                PostStockTag.symbol == symbol
            )
        if cursor_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    Post.created_at < cursor_at,
                    and_(Post.created_at == cursor_at, Post.id < cursor_id),
                )
            )
        stmt = stmt.order_by(Post.created_at.desc(), Post.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_tags_for_posts(self, post_ids: list[str]) -> dict[str, list[str]]:
        if not post_ids:
            return {}
        result = await self.db.execute(
            select(PostStockTag.post_id, PostStockTag.symbol).where(
                PostStockTag.post_id.in_(post_ids)
            )
        )
        mapping: dict[str, list[str]] = {}
        for post_id, symbol in result.all():
            mapping.setdefault(post_id, []).append(symbol)
        for symbols in mapping.values():
            symbols.sort()
        return mapping

    # ── Likes ─────────────────────────────────────────────────────────────────
    async def get_user_liked_post_ids(self, post_ids: list[str], user_id: str) -> set[str]:
        if not post_ids:
            return set()
        result = await self.db.execute(
            select(PostLike.post_id).where(
                PostLike.post_id.in_(post_ids),
                PostLike.user_id == user_id,
            )
        )
        return {row[0] for row in result.all()}

    async def get_like(self, post_id: str, user_id: str) -> PostLike | None:
        result = await self.db.execute(
            select(PostLike).where(
                PostLike.post_id == post_id,
                PostLike.user_id == user_id,
            )
        )
        return result.scalars().first()

    async def set_like(self, post_id: str, user_id: str, liked: bool) -> None:
        if liked:
            self.db.add(PostLike(post_id=post_id, user_id=user_id))
        else:
            await self.db.execute(
                delete(PostLike).where(
                    PostLike.post_id == post_id,
                    PostLike.user_id == user_id,
                )
            )
        await self.db.flush()

    # ── Comments ──────────────────────────────────────────────────────────────
    async def get_comment(self, comment_id: str) -> Comment | None:
        result = await self.db.execute(
            select(Comment).where(Comment.id == comment_id)
        )
        return result.scalars().first()

    async def create_comment(
        self,
        post_id: str,
        user_id: str,
        content: str,
        parent_comment_id: str | None = None,
    ) -> Comment:
        comment = Comment(
            post_id=post_id,
            user_id=user_id,
            content=content,
            parent_comment_id=parent_comment_id,
        )
        self.db.add(comment)
        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def get_top_level_comments(
        self,
        post_id: str,
        cursor_at: datetime | None = None,
        cursor_id: str | None = None,
        limit: int = 20,
    ) -> list[Comment]:
        stmt = (
            select(Comment)
            .options(selectinload(Comment.author))
            .where(
                Comment.post_id == post_id,
                Comment.parent_comment_id.is_(None),
                Comment.status == "PUBLISHED",
            )
        )
        if cursor_at is not None and cursor_id is not None:
            stmt = stmt.where(
                or_(
                    Comment.created_at < cursor_at,
                    and_(Comment.created_at == cursor_at, Comment.id < cursor_id),
                )
            )
        stmt = stmt.order_by(Comment.created_at.desc(), Comment.id.desc()).limit(limit)
        result = await self.db.execute(stmt)
        return list(result.scalars().all())

    async def get_replies(self, parent_ids: list[str]) -> list[Comment]:
        if not parent_ids:
            return []
        result = await self.db.execute(
            select(Comment)
            .options(selectinload(Comment.author))
            .where(
                Comment.parent_comment_id.in_(parent_ids),
                Comment.status == "PUBLISHED",
            )
            .order_by(Comment.created_at.asc(), Comment.id.asc())
        )
        return list(result.scalars().all())

    async def set_comment_status(self, comment_id: str, status: str) -> None:
        await self.db.execute(
            update(Comment).where(Comment.id == comment_id).values(status=status)
        )

    # ── Reports ───────────────────────────────────────────────────────────────
    async def get_report(
        self,
        reporter_user_id: str,
        target_type: str,
        target_id: str,
    ) -> Report | None:
        result = await self.db.execute(
            select(Report).where(
                Report.reporter_user_id == reporter_user_id,
                Report.target_type == target_type,
                Report.target_id == target_id,
            )
        )
        return result.scalars().first()

    async def create_report(
        self,
        reporter_user_id: str,
        target_type: str,
        target_id: str,
        reason: str,
    ) -> Report:
        report = Report(
            reporter_user_id=reporter_user_id,
            target_type=target_type,
            target_id=target_id,
            reason=reason,
        )
        self.db.add(report)
        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def count_reports(self, target_type: str, target_id: str) -> int:
        result = await self.db.execute(
            select(func.count(Report.id)).where(
                Report.target_type == target_type,
                Report.target_id == target_id,
                Report.status != "DISMISSED",
            )
        )
        return result.scalar() or 0

    # ── Share links ───────────────────────────────────────────────────────────
    async def create_share_link(
        self,
        short_code: str,
        post_id: str,
        created_by: str,
    ) -> ShareLink:
        link = ShareLink(short_code=short_code, post_id=post_id, created_by=created_by)
        self.db.add(link)
        await self.db.flush()
        return link

    async def get_share_link(self, short_code: str) -> ShareLink | None:
        result = await self.db.execute(
            select(ShareLink).where(ShareLink.short_code == short_code)
        )
        return result.scalars().first()

    # ── Users ─────────────────────────────────────────────────────────────────
    async def get_user(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()