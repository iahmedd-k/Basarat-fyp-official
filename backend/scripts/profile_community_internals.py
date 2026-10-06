import asyncio
import time
from sqlalchemy import select, func, text, desc, distinct
from app.db.session import async_session_factory
from app.models.user import User
from app.models.community import (
    CommunityPost,
    CommunityPostLike,
    CommunityPostTicker,
    CommunityBookmark,
    CommunityComment,
    CommunityFollow,
    CommunityNotification,
    PostStatus,
)
from app.services.community_service import CommunityService
from app.services.trending_service import TrendingService
from app.core.redis import get_redis_client

async def profile_all():
    async with async_session_factory() as session:
        # Get demo user
        res = await session.execute(select(User).where(User.email == "demo@basarat.pk"))
        user = res.scalars().first()
        if not user:
            print("Demo user not found!")
            return
        user_id = user.id
        print(f"Profiling for user: {user.email} (id: {user_id})")

        service = CommunityService(session)

        # 1. Profile Trending Tickers
        t0 = time.perf_counter()
        tickers = await TrendingService.get_trending_tickers(session, limit=10)
        t_tick = (time.perf_counter() - t0) * 1000
        print(f"1. TrendingService.get_trending_tickers -> {t_tick:.2f}ms (count: {len(tickers)})")

        # 2. Profile Trending Posts
        t0 = time.perf_counter()
        trending_post_ids = await TrendingService.get_trending_posts(session, limit=10)
        t_posts = (time.perf_counter() - t0) * 1000
        print(f"2. TrendingService.get_trending_posts -> {t_posts:.2f}ms (count: {len(trending_post_ids)})")

        # 3. Profile Feed Query
        t0 = time.perf_counter()
        posts, cursor, has_more = await service.get_feed(current_user_id=user_id, limit=20)
        t_feed = (time.perf_counter() - t0) * 1000
        print(f"3. CommunityService.get_feed -> {t_feed:.2f}ms (count: {len(posts)})")

        # 4. Profile User Profile Stats
        t0 = time.perf_counter()
        stats = await service.get_user_profile_stats(user_id, user_id)
        t_stats = (time.perf_counter() - t0) * 1000
        print(f"4. CommunityService.get_user_profile_stats -> {t_stats:.2f}ms (stats: {stats})")

        # 5. Profile User Posts
        t0 = time.perf_counter()
        user_posts, cursor, has_more = await service.get_user_posts(user_id, user_id, limit=20)
        t_up = (time.perf_counter() - t0) * 1000
        print(f"5. CommunityService.get_user_posts -> {t_up:.2f}ms (count: {len(user_posts)})")

        # 6. Profile Notifications
        t0 = time.perf_counter()
        notifs, total = await service.get_notifications(user_id, page=1, limit=20)
        t_notif = (time.perf_counter() - t0) * 1000
        print(f"6. CommunityService.get_notifications -> {t_notif:.2f}ms (count: {len(notifs)}, total: {total})")

        # 7. Check Postgres community tables indexes and counts
        counts = {}
        for tbl in ["community_posts", "community_comments", "community_post_likes", "community_post_tickers", "community_follows", "community_notifications", "community_bookmarks", "community_reports"]:
            r = await session.execute(text(f"SELECT count(*) FROM {tbl}"))
            counts[tbl] = r.scalar()
        print(f"7. Table Counts: {counts}")

if __name__ == "__main__":
    asyncio.run(profile_all())
