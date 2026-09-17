from datetime import datetime

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.community import Comment, Post, Report, Vote
from app.models.user import User


class CommunityRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_post(self, user_id: str, symbol: str, stance: str, rationale_text: str) -> Post:
        post = Post(
            user_id=user_id,
            symbol=symbol.upper(),
            stance=stance,
            rationale_text=rationale_text,
        )
        self.db.add(post)
        await self.db.flush()
        await self.db.refresh(post)
        return post

    async def get_post(self, post_id: str) -> Post | None:
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.author), selectinload(Post.comments))
            .where(Post.id == post_id)
        )
        return result.scalars().first()

    async def get_post_for_feed(self, post_id: str) -> Post | None:
        result = await self.db.execute(
            select(Post)
            .options(selectinload(Post.author))
            .where(Post.id == post_id)
        )
        return result.scalars().first()

    async def get_feed(
        self,
        page: int = 1,
        limit: int = 20,
        symbol: str | None = None,
    ) -> tuple[list[Post], int]:
        query = select(Post).options(selectinload(Post.author))

        if symbol:
            query = query.where(Post.symbol == symbol.upper())

        count_query = select(func.count(Post.id))
        if symbol:
            count_query = count_query.where(Post.symbol == symbol.upper())

        total_result = await self.db.execute(count_query)
        total = total_result.scalar() or 0

        query = query.order_by(Post.created_at.desc())
        query = query.offset((page - 1) * limit).limit(limit)

        result = await self.db.execute(query)
        posts = list(result.scalars().all())

        return posts, total

    async def create_comment(self, post_id: str, user_id: str, text: str) -> Comment:
        comment = Comment(post_id=post_id, user_id=user_id, text=text)
        self.db.add(comment)

        await self.db.execute(
            update(Post).where(Post.id == post_id).values(comment_count=Post.comment_count + 1)
        )

        await self.db.flush()
        await self.db.refresh(comment)
        return comment

    async def get_comments(self, post_id: str) -> list[Comment]:
        result = await self.db.execute(
            select(Comment)
            .options(selectinload(Comment.author))
            .where(Comment.post_id == post_id)
            .order_by(Comment.created_at.desc())
        )
        return list(result.scalars().all())

    async def get_user_vote(self, post_id: str, user_id: str) -> Vote | None:
        result = await self.db.execute(
            select(Vote).where(Vote.post_id == post_id, Vote.user_id == user_id)
        )
        return result.scalars().first()

    async def upsert_vote(self, post_id: str, user_id: str, direction: str) -> Vote:
        existing = await self.get_user_vote(post_id, user_id)

        if existing:
            if existing.direction == direction:
                await self.db.delete(existing)
                if direction == "up":
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(upvotes=Post.upvotes - 1)
                    )
                else:
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(downvotes=Post.downvotes - 1)
                    )
                await self.db.flush()
                return None
            else:
                old_dir = existing.direction
                existing.direction = direction
                if old_dir == "up":
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(upvotes=Post.upvotes - 1)
                    )
                else:
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(downvotes=Post.downvotes - 1)
                    )
                if direction == "up":
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(upvotes=Post.upvotes + 1)
                    )
                else:
                    await self.db.execute(
                        update(Post).where(Post.id == post_id).values(downvotes=Post.downvotes + 1)
                    )
                await self.db.flush()
                await self.db.refresh(existing)
                return existing
        else:
            vote = Vote(post_id=post_id, user_id=user_id, direction=direction)
            self.db.add(vote)
            if direction == "up":
                await self.db.execute(
                    update(Post).where(Post.id == post_id).values(upvotes=Post.upvotes + 1)
                )
            else:
                await self.db.execute(
                    update(Post).where(Post.id == post_id).values(downvotes=Post.downvotes + 1)
                )
            await self.db.flush()
            await self.db.refresh(vote)
            return vote

    async def get_leaderboard(
        self, since: datetime | None = None, limit: int = 100
    ) -> list[dict]:
        query = (
            select(
                Post.user_id,
                func.count(Post.id).label("post_count"),
                func.sum(Post.upvotes - Post.downvotes).label("total_score"),
                func.sum(Post.upvotes).label("upvotes_received"),
            )
            .group_by(Post.user_id)
        )

        if since:
            query = query.where(Post.created_at >= since)

        query = query.order_by(func.sum(Post.upvotes - Post.downvotes).desc())
        query = query.limit(limit)

        result = await self.db.execute(query)
        rows = result.all()

        if not rows:
            return []

        user_ids = [row.user_id for row in rows]
        users_result = await self.db.execute(
            select(User).where(User.id.in_(user_ids))
        )
        user_map = {u.id: u for u in users_result.scalars().all()}

        entries = []
        for i, row in enumerate(rows, start=1):
            user = user_map.get(row.user_id)
            entries.append({
                "user_id": row.user_id,
                "username": user.username if user else None,
                "avatar_url": user.avatar_url if user else None,
                "post_count": row.post_count,
                "total_score": int(row.total_score or 0),
                "upvotes_received": int(row.upvotes_received or 0),
                "rank": i,
            })

        return entries

    async def create_report(self, post_id: str, user_id: str, reason: str) -> Report:
        existing = await self.db.execute(
            select(Report).where(Report.post_id == post_id, Report.user_id == user_id)
        )
        if existing.scalars().first() is not None:
            return None

        report = Report(post_id=post_id, user_id=user_id, reason=reason)
        self.db.add(report)

        await self.db.execute(
            update(Post).where(Post.id == post_id).values(is_reported=True)
        )

        await self.db.flush()
        await self.db.refresh(report)
        return report

    async def get_user_by_id(self, user_id: str) -> User | None:
        result = await self.db.execute(select(User).where(User.id == user_id))
        return result.scalars().first()
