from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.dialects import postgresql

from app.services.community_service import CommunityService


@pytest.mark.asyncio
async def test_batch_fetch_post_interactions_uses_one_query():
    result = MagicMock()
    result.all.return_value = [
        ("post-liked", "like"),
        ("post-bookmarked", "bookmark"),
    ]
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    service = CommunityService(db)

    liked, bookmarked = await service.batch_fetch_post_interactions(
        ["post-liked", "post-bookmarked"],
        "user-1",
    )

    assert liked == {"post-liked"}
    assert bookmarked == {"post-bookmarked"}
    db.execute.assert_awaited_once()
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "UNION ALL" in sql
    assert "community_post_likes" in sql
    assert "community_bookmarks" in sql


@pytest.mark.asyncio
async def test_batch_fetch_post_interactions_skips_query_without_inputs():
    db = SimpleNamespace(execute=AsyncMock())
    service = CommunityService(db)

    liked, bookmarked = await service.batch_fetch_post_interactions([], "user-1")

    assert liked == set()
    assert bookmarked == set()
    db.execute.assert_not_awaited()


@pytest.mark.asyncio
async def test_get_notifications_returns_window_count_from_one_query():
    notification = object()
    result = MagicMock()
    result.all.return_value = [(notification, 3)]
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    service = CommunityService(db)

    notifications, total = await service.get_notifications("user-1", unread_only=True)

    assert notifications == [notification]
    assert total == 3
    db.execute.assert_awaited_once()
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "OVER" in sql
    assert "community_notifications.is_read" in sql


@pytest.mark.asyncio
async def test_get_notifications_preserves_total_for_empty_out_of_range_page():
    page_result = MagicMock()
    page_result.all.return_value = []
    count_result = MagicMock()
    count_result.scalar.return_value = 3
    db = SimpleNamespace(execute=AsyncMock(side_effect=[page_result, count_result]))
    service = CommunityService(db)

    notifications, total = await service.get_notifications("user-1", page=2, limit=20)

    assert notifications == []
    assert total == 3
    assert db.execute.await_count == 2


@pytest.mark.asyncio
async def test_get_user_profile_with_stats_uses_one_query():
    target_user = object()
    result = MagicMock()
    result.first.return_value = (target_user, 5, 8, 2, 1)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    service = CommunityService(db)

    user, stats = await service.get_user_profile_with_stats("user-2", "user-1")

    assert user is target_user
    assert stats == {
        "followers_count": 8,
        "following_count": 2,
        "published_post_count": 5,
        "is_following": True,
        "is_own_profile": False,
    }
    db.execute.assert_awaited_once()
