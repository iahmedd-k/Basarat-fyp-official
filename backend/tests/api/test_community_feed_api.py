"""Community feed route checks, including page-level like enrichment."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.community import CommunityPost, CommunityPostLike
from app.models.user import User


@pytest.mark.api
async def test_community_feed_variants_return_posts_and_likes(
    client: AsyncClient,
    auth_headers: dict,
    test_user: User,
    db_session: AsyncSession,
):
    general = CommunityPost(
        author_id=test_user.id,
        post_type="GENERAL_MARKET",
        content="Market breadth improved across the exchange.",
        status="PUBLISHED",
    )
    stock = CommunityPost(
        author_id=test_user.id,
        post_type="STOCK",
        stock_symbol="OGDC",
        content="OGDC reported stronger trading activity.",
        status="PUBLISHED",
    )
    db_session.add_all([general, stock])
    await db_session.flush()
    db_session.add(CommunityPostLike(post_id=stock.id, user_id=test_user.id))
    await db_session.flush()

    routes = [
        "/api/v1/community/feed",
        "/api/v1/community/posts/search?q=market",
        "/api/v1/community/posts/market",
        "/api/v1/community/posts/stock/OGDC",
        "/api/v1/community/me/posts",
        f"/api/v1/community/users/{test_user.id}/posts",
    ]
    for route in routes:
        response = await client.get(route, headers=auth_headers)
        assert response.status_code == 200, f"{route}: {response.text}"
        payload = response.json()
        assert isinstance(payload["posts"], list)
        if "stock/OGDC" in route:
            assert len(payload["posts"]) == 1
            assert payload["posts"][0]["stock_symbol"] == "OGDC"
            assert payload["posts"][0]["liked_by_me"] is True

