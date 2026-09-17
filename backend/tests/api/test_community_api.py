"""API tests for community endpoints."""

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import hash_password
from app.models.community import Post
from app.models.user import User


@pytest.mark.api
class TestCommunityFeed:
    async def test_get_feed_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["posts"] == []
        assert data["total"] == 0
        assert data["has_more"] is False

    async def test_get_feed_with_posts(self, client: AsyncClient, auth_headers, db_session: AsyncSession):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Strong fundamentals")
        db_session.add(post)
        await db_session.flush()

        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["posts"]) == 1
        assert data["posts"][0]["symbol"] == "HBL"
        assert data["posts"][0]["stance"] == "bullish"
        assert data["posts"][0]["upvotes"] == 0

    async def test_get_feed_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/community/feed")
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestCommunityPosts:
    async def test_create_post(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"symbol": "HBL", "stance": "bullish", "rationale_text": "Strong fundamentals and growth potential"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["symbol"] == "HBL"
        assert data["stance"] == "bullish"
        assert data["rationale_text"] == "Strong fundamentals and growth potential"
        assert data["upvotes"] == 0
        assert data["downvotes"] == 0
        assert data["comment_count"] == 0

    async def test_create_post_empty_content(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"symbol": "", "stance": "bullish", "rationale_text": ""},
        )
        assert resp.status_code == 422

    async def test_create_post_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/community/posts",
            json={"symbol": "HBL", "stance": "bullish", "rationale_text": "test content here"},
        )
        assert resp.status_code in (401, 403)


@pytest.mark.api
class TestCommunityVote:
    async def test_vote_up_on_post(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Vote on me")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["upvotes"] == 1
        assert data["downvotes"] == 0
        assert data["score"] == 1
        assert data["direction"] == "up"

    async def test_vote_toggle_removes_vote(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Toggle vote")
        db_session.add(post)
        await db_session.flush()

        await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["upvotes"] == 0
        assert data["direction"] is None

    async def test_vote_switch_direction(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Switch vote")
        db_session.add(post)
        await db_session.flush()

        await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "down"},
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["upvotes"] == 0
        assert data["downvotes"] == 1
        assert data["score"] == -1

    async def test_vote_invalid_direction(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Vote test")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "sideways"},
        )
        assert resp.status_code == 422

    async def test_vote_own_post_rejected(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Own post vote")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        assert resp.status_code == 400

    async def test_vote_nonexistent_post(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts/nonexistent/vote",
            headers=auth_headers,
            json={"direction": "up"},
        )
        assert resp.status_code == 404


@pytest.mark.api
class TestCommunityComments:
    async def test_get_comments_empty(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Comments here")
        db_session.add(post)
        await db_session.flush()

        resp = await client.get(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["comments"] == []
        assert data["total"] == 0

    async def test_add_comment(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Add comment")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"text": "Great analysis!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["text"] == "Great analysis!"
        assert data["post_id"] == post.id

    async def test_add_comment_increments_count(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Count test")
        db_session.add(post)
        await db_session.flush()

        await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"text": "First comment"},
        )
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"text": "Second comment"},
        )
        assert resp.status_code == 201

        feed_resp = await client.get(
            "/api/v1/community/feed",
            headers=auth_headers,
        )
        posts = feed_resp.json()["posts"]
        matching = [p for p in posts if p["id"] == post.id]
        assert len(matching) == 1
        assert matching[0]["comment_count"] == 2


@pytest.mark.api
class TestCommunityLeaderboard:
    async def test_get_leaderboard(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/community/leaderboard", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert "entries" in data
        assert data["period"] == "all_time"

    async def test_get_leaderboard_weekly(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/community/leaderboard?period=weekly", headers=auth_headers)
        assert resp.status_code == 200
        assert resp.json()["period"] == "weekly"

    async def test_get_leaderboard_invalid_period(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/community/leaderboard?period=yearly", headers=auth_headers)
        assert resp.status_code == 422


@pytest.mark.api
class TestCommunityReport:
    async def test_report_post(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Report me")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/report",
            headers=auth_headers,
            json={"reason": "Spam content"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["reason"] == "Spam content"
        assert data["post_id"] == post.id

    async def test_report_own_post_rejected(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        post = Post(user_id=test_user.id, symbol="HBL", stance="bullish", rationale_text="Self report")
        db_session.add(post)
        await db_session.flush()

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/report",
            headers=auth_headers,
            json={"reason": "Self reporting"},
        )
        assert resp.status_code == 400

    async def test_duplicate_report_rejected(self, client: AsyncClient, auth_headers, db_session: AsyncSession, test_user: User):
        other = User(email="other@test.com", username="other", hashed_password=hash_password("pass"))
        db_session.add(other)
        await db_session.flush()

        post = Post(user_id=other.id, symbol="HBL", stance="bullish", rationale_text="Dupe report")
        db_session.add(post)
        await db_session.flush()

        await client.post(
            f"/api/v1/community/posts/{post.id}/report",
            headers=auth_headers,
            json={"reason": "First report"},
        )
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/report",
            headers=auth_headers,
            json={"reason": "Second report"},
        )
        assert resp.status_code == 409
