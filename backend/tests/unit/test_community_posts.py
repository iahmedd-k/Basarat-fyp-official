from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request

from app.api.v1.community.posts import create_post
from app.schemas.community import PostType


@pytest.mark.asyncio
async def test_create_post_response_does_not_reload_post_details():
    now = datetime.now(timezone.utc)
    post = SimpleNamespace(
        id="post-1",
        author_id="user-1",
        post_type=PostType.GENERAL_MARKET.value,
        stock_symbol=None,
        stock=None,
        tickers=[],
        price_at_post=None,
        content="Market update",
        image_url=None,
        media_metadata=None,
        like_count=0,
        comment_count=0,
        report_count=0,
        view_count=0,
        bookmark_count=0,
        is_edited=False,
        edited_at=None,
        status="PUBLISHED",
        removed_reason=None,
        created_at=now,
        updated_at=now,
    )
    service = SimpleNamespace(
        create_post=AsyncMock(return_value=post),
        get_post_with_details=AsyncMock(),
    )
    user = SimpleNamespace(
        id="user-1",
        username="trader",
        full_name="Trader One",
        avatar_url="",
        is_verified=False,
    )
    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/community/posts",
            "headers": [],
            "query_string": b"",
        }
    )

    response = await create_post(
        request=request,
        content="Market update",
        post_type=PostType.GENERAL_MARKET,
        stock_symbol=None,
        image=None,
        idempotency_key=None,
        user=user,
        service=service,
    )

    assert response.id == post.id
    assert response.author_username == user.username
    assert response.author.id == user.id
    assert response.view_count == 0
    assert not response.liked_by_me
    assert not response.bookmarked_by_me
    service.create_post.assert_awaited_once()
    service.get_post_with_details.assert_not_awaited()
