from datetime import datetime, timezone
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from starlette.requests import Request
from sqlalchemy import select

from app.api.v1.community.posts import create_post
from app.models.community import CommunityPostTicker
from app.models.stock import Stock
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


@pytest.mark.asyncio
async def test_create_post_with_cashtag_returns_tickers(
    client, auth_headers, db_session
):
    stock = await db_session.scalar(select(Stock).where(Stock.symbol == "OGDC"))
    if stock is None:
        db_session.add(
            Stock(
                symbol="OGDC",
                name="Oil & Gas Development Company",
                sector="Oil & Gas Exploration",
            )
        )
    else:
        stock.is_active = True
    await db_session.flush()

    response = await client.post(
        "/api/v1/community/posts",
        headers=auth_headers,
        data={
            "content": "Watching $OGDC closely",
            "post_type": "GENERAL_MARKET",
        },
    )

    assert response.status_code == 201, response.text
    post_id = response.json()["id"]
    assert response.json()["tickers"] == ["OGDC"]

    ticker_rows = await db_session.execute(
        select(CommunityPostTicker).where(CommunityPostTicker.post_id == post_id)
    )
    assert [row.ticker for row in ticker_rows.scalars()] == ["OGDC"]


@pytest.mark.asyncio
async def test_delete_own_comment(client, auth_headers):
    post_response = await client.post(
        "/api/v1/community/posts",
        headers=auth_headers,
        data={
            "content": "Post for comment deletion regression",
            "post_type": "GENERAL_MARKET",
        },
    )
    assert post_response.status_code == 201, post_response.text
    post_id = post_response.json()["id"]

    comment_response = await client.post(
        f"/api/v1/community/posts/{post_id}/comments",
        headers=auth_headers,
        json={"content": "Comment to delete"},
    )
    assert comment_response.status_code == 201, comment_response.text
    comment_id = comment_response.json()["id"]

    delete_response = await client.delete(
        f"/api/v1/community/comments/{comment_id}",
        headers=auth_headers,
    )
    assert delete_response.status_code == 204, delete_response.text

    comments_response = await client.get(
        f"/api/v1/community/posts/{post_id}/comments",
        headers=auth_headers,
    )
    assert comments_response.status_code == 200, comments_response.text
    assert all(
        comment["id"] != comment_id
        for comment in comments_response.json()["comments"]
    )
