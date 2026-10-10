from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.dialects import postgresql

from app.core.exceptions import NotFoundError
from app.models.community import NotificationType
from app.services import counter_service, community_service
from app.services.counter_service import CounterService
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
async def test_get_comments_checks_access_and_counts_replies_in_one_query():
    created_at = datetime.now(timezone.utc)
    comment = SimpleNamespace(id="comment-1", created_at=created_at)

    post_check_res = MagicMock()
    post_check_res.scalar_one_or_none.return_value = "post-1"

    comments_res = MagicMock()
    comments_res.scalars.return_value.unique.return_value.all.return_value = [comment]

    reply_res = MagicMock()
    reply_res.all.return_value = [("comment-1", 4)]

    db = SimpleNamespace(execute=AsyncMock(side_effect=[post_check_res, comments_res, reply_res]))
    service = CommunityService(db)

    comments, cursor, has_more, reply_counts = await service.get_comments(
        "post-1",
        current_user_id="user-1",
    )

    assert comments == [comment]
    assert cursor == f"{created_at.isoformat()}|comment-1"
    assert not has_more
    assert reply_counts == {"comment-1": 4}
    assert db.execute.await_count == 3


@pytest.mark.asyncio
async def test_get_comments_raises_not_found_when_post_is_missing_or_hidden():
    post_check_res = MagicMock()
    post_check_res.scalar_one_or_none.return_value = None
    db = SimpleNamespace(execute=AsyncMock(return_value=post_check_res))
    service = CommunityService(db)

    with pytest.raises(NotFoundError, match="Post not found"):
        await service.get_comments("missing-post", current_user_id="user-1")

    db.execute.assert_awaited_once()


@pytest.mark.asyncio
async def test_get_post_with_details_fetches_interaction_flags_in_post_query(monkeypatch):
    post = object()
    result = MagicMock()
    result.first.return_value = (post, True, False)
    db = SimpleNamespace(execute=AsyncMock(return_value=result))
    service = CommunityService(db)
    increment_view = AsyncMock()
    monkeypatch.setattr(community_service.CounterService, "increment_post_view", increment_view)

    details = await service.get_post_with_details("post-1", current_user_id="user-1")

    assert details == {
        "post": post,
        "liked_by_me": True,
        "bookmarked_by_me": False,
    }
    db.execute.assert_awaited_once()
    increment_view.assert_awaited_once_with("post-1", 1)
    sql = str(db.execute.await_args.args[0].compile(dialect=postgresql.dialect()))
    assert "EXISTS" in sql
    assert "community_post_likes" in sql
    assert "community_bookmarks" in sql


@pytest.mark.asyncio
async def test_flush_buffered_counters_uses_one_update_per_counter_type(monkeypatch):
    redis = SimpleNamespace(
        hgetall=AsyncMock(
            side_effect=[
                {"post-1": "2", "post-2": "-1"},
                {"post-1": "3"},
                {"post-2": "4"},
            ]
        ),
        delete=AsyncMock(),
    )
    execute = AsyncMock()
    session = SimpleNamespace(execute=execute, flush=AsyncMock())
    monkeypatch.setattr(counter_service, "get_redis_client", lambda: redis)

    flushed = await CounterService.flush_buffered_counters_to_db(session)

    assert flushed == {"likes": 2, "comments": 1, "views": 1}
    assert execute.await_count == 3
    assert redis.delete.await_count == 3
    for call in execute.await_args_list:
        sql = str(call.args[0].compile(dialect=postgresql.dialect()))
        assert "CASE community_posts.id" in sql
        assert "community_posts.id IN" in sql
    session.flush.assert_awaited_once()


@pytest.mark.asyncio
async def test_new_comment_notification_skips_redundant_deduplication_query():
    db = SimpleNamespace(
        execute=AsyncMock(),
        add=MagicMock(),
        flush=AsyncMock(),
    )
    service = CommunityService(db)

    with patch("app.core.task_runner.dispatch_task"):
        notification = await service._create_notification(
            recipient_id="user-2",
            type=NotificationType.POST_COMMENTED,
            title="New Comment",
            message="Someone commented on your post",
            post_id="post-1",
            comment_id="new-comment",
            actor_id="user-1",
            check_existing=False,
        )

    assert notification.comment_id == "new-comment"
    db.execute.assert_not_awaited()
    db.add.assert_called_once_with(notification)
    db.flush.assert_awaited_once()


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
