"""API tests for community endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import create_access_token, hash_password
from app.models.community import Post, PostStockTag
from app.models.user import User


def _headers_for(user_id: str) -> dict:
    token = create_access_token({"sub": user_id})
    return {"Authorization": f"Bearer {token}"}


async def _create_user(db: AsyncSession, email: str) -> User:
    user = User(
        email=email,
        username=email.split("@")[0],
        hashed_password=hash_password("TestPass123!"),
        full_name="Test User",
    )
    db.add(user)
    await db.flush()
    await db.refresh(user)
    return user


async def _seed_post(
    db: AsyncSession,
    author: User,
    *,
    symbols: tuple[str, ...] = ("HBL",),
    content: str = "HBL is looking strong.",
    status: str = "PUBLISHED",
    created_at: datetime | None = None,
    sentiment: str | None = None,
) -> Post:
    post = Post(
        user_id=author.id,
        content=content,
        status=status,
        sentiment=sentiment,
        created_at=created_at or datetime.now(timezone.utc),
    )
    db.add(post)
    await db.flush()
    for symbol in symbols:
        db.add(PostStockTag(post_id=post.id, symbol=symbol))
    await db.flush()
    return post


@pytest.fixture(autouse=True)
def _bypass_post_ratelimit():
    """Never rate-limit by default; dedicated test covers the 429 path."""
    with patch(
        "app.services.community_service.acquire_post_slot",
        new=AsyncMock(return_value=0),
    ):
        yield


@pytest.mark.api
class TestCommunityCreatePost:
    async def test_create_post(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={
                "content": "HBL is looking strong this quarter.",
                "symbols": ["hbl", "UBL"],
                "sentiment": "BULLISH",
            },
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["content"] == "HBL is looking strong this quarter."
        assert data["symbols"] == ["HBL", "UBL"]
        assert data["sentiment"] == "BULLISH"
        assert data["likeCount"] == 0
        assert data["commentCount"] == 0
        assert data["likedByMe"] is False
        assert data["createdAt"].endswith("Z")
        assert data["userId"]

    async def test_create_post_requires_1_to_3_symbols(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "No ticker here"},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_STOCK_TAG"

        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "Too many tickers", "symbols": ["HBL", "UBL", "MCB", "OGDC"]},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_STOCK_TAG"

    async def test_create_post_rejects_unknown_symbol(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "Fake ticker", "symbols": ["HBL", "FAKE"]},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "INVALID_STOCK_TAG"
        assert body["field"] == "symbols"

    async def test_create_post_rejects_flagged_content(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "this is total bullshit", "symbols": ["HBL"]},
        )
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"] == "CONTENT_REJECTED"
        assert body["field"] == "content"

    async def test_create_post_rate_limited(
        self, client: AsyncClient, auth_headers
    ):
        with patch(
            "app.services.community_service.acquire_post_slot",
            new=AsyncMock(return_value=12),
        ):
            resp = await client.post(
                "/api/v1/community/posts",
                headers=auth_headers,
                json={"content": "One more post", "symbols": ["HBL"]},
            )
        assert resp.status_code == 429
        body = resp.json()
        assert body["error"] == "RATE_LIMITED"
        assert body["retryAfterSeconds"] == 12

    async def test_create_post_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/community/posts",
            json={"content": "Anon post", "symbols": ["HBL"]},
        )
        assert resp.status_code in (401, 403)

    async def test_create_post_with_cloudinary_media_url(
        self, client: AsyncClient, auth_headers
    ):
        from app.core.config import get_settings

        cloud = get_settings().CLOUDINARY_CLOUD_NAME or "basarat"
        url = f"https://res.cloudinary.com/{cloud}/image/upload/v1720000000000/community/chart.jpg"
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={"content": "Chart included", "symbols": ["HBL"], "mediaUrl": url},
        )
        assert resp.status_code == 201
        assert resp.json()["mediaUrl"] == url

    async def test_create_post_rejects_non_cloudinary_media_url(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/community/posts",
            headers=auth_headers,
            json={
                "content": "Hotlinked chart",
                "symbols": ["HBL"],
                "mediaUrl": "https://cdn.example.com/chart.png",
            },
        )
        assert resp.status_code == 422

    async def test_create_post_rejects_foreign_cloudinary_media_url(
        self, client: AsyncClient, auth_headers
    ):
        fake_settings = type(
            "FakeSettings", (), {"CLOUDINARY_CLOUD_NAME": "basarat-cloud"}
        )()
        with patch(
            "app.services.community_service.get_settings", return_value=fake_settings
        ):
            resp = await client.post(
                "/api/v1/community/posts",
                headers=auth_headers,
                json={
                    "content": "Wrong cloud",
                    "symbols": ["HBL"],
                    "mediaUrl": "https://res.cloudinary.com/other/image/upload/v1/community/x.jpg",
                },
            )
        assert resp.status_code == 422
        assert resp.json()["error"] == "INVALID_MEDIA_URL"


_PNG_1PX = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c63600000000001000300000000937a4d4c0000000049454e44ae426082"
)


@pytest.mark.api
class TestCommunityMediaUpload:
    async def test_media_upload_requires_auth(self, client: AsyncClient):
        resp = await client.post(
            "/api/v1/community/media",
            files={"file": ("chart.png", _PNG_1PX, "image/png")},
        )
        assert resp.status_code in (401, 403)

    async def test_media_upload_rejects_non_image(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/community/media",
            headers=auth_headers,
            files={"file": ("notes.txt", b"not an image at all", "text/plain")},
        )
        assert resp.status_code == 400
        body = resp.json()
        assert body["error"] == "INVALID_IMAGE"
        assert body["field"] == "image"

    async def test_media_upload_rejects_empty_file(
        self, client: AsyncClient, auth_headers
    ):
        resp = await client.post(
            "/api/v1/community/media",
            headers=auth_headers,
            files={"file": ("blank.png", b"", "image/png")},
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_IMAGE"

    async def test_media_upload_rejects_oversized_image(
        self, client: AsyncClient, auth_headers
    ):
        from app.core.config import get_settings

        oversize = b"\xff\xd8\xff" + b"\x00" * (get_settings().MAX_FILE_SIZE_MB * 1_000_000 + 1)
        resp = await client.post(
            "/api/v1/community/media",
            headers=auth_headers,
            files={"file": ("big.jpg", oversize, "image/jpeg")},
        )
        assert resp.status_code == 413
        assert resp.json()["error"] == "IMAGE_TOO_LARGE"

    async def test_media_upload_unavailable_without_cloudinary_credentials(
        self, client: AsyncClient, auth_headers
    ):
        from app.services.media_service import MediaService

        with patch.object(MediaService, "_cloudinary_configured", return_value=False):
            resp = await client.post(
                "/api/v1/community/media",
                headers=auth_headers,
                files={"file": ("chart.png", _PNG_1PX, "image/png")},
            )
        assert resp.status_code == 503
        assert resp.json()["error"] == "MEDIA_UPLOAD_UNAVAILABLE"


@pytest.mark.api
class TestCommunityFeed:
    async def test_get_feed_empty(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert data["items"] == []
        assert data["nextCursor"] is None

    async def test_get_feed_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/community/feed")
        assert resp.status_code in (401, 403)

    async def test_get_feed_with_posts(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "author@test.com")
        await _seed_post(db_session, other, symbols=("HBL", "UBL"))

        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["items"]) == 1
        item = data["items"][0]
        assert item["content"] == "HBL is looking strong."
        assert item["user"]["username"] == "author"
        assert [q["symbol"] for q in item["symbols"]] == ["HBL", "UBL"]
        assert item["symbols"][0]["price"] == 154.0
        assert item["likeCount"] == 0
        assert item["likedByMe"] is False

    async def test_get_feed_excludes_flagged_and_removed(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "author2@test.com")
        published = await _seed_post(db_session, other, content="Visible post")
        await _seed_post(db_session, other, content="Flagged post", status="FLAGGED")
        await _seed_post(db_session, other, content="Removed post", status="REMOVED")

        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["id"] == published.id

    async def test_get_feed_following_behaves_like_all(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "author3@test.com")
        await _seed_post(db_session, other)

        resp = await client.get(
            "/api/v1/community/feed?filter=following", headers=auth_headers
        )
        assert resp.status_code == 200
        assert len(resp.json()["items"]) == 1

    async def test_feed_cursor_pagination(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "paginator@test.com")
        base = datetime(2026, 1, 3, 12, 0, 0, tzinfo=timezone.utc)
        await _seed_post(db_session, other, content="Newest", created_at=base)
        await _seed_post(db_session, other, content="Middle", created_at=base.replace(day=2))
        p3 = await _seed_post(
            db_session, other, content="Oldest", created_at=base.replace(day=1)
        )

        page1 = await client.get(
            "/api/v1/community/feed?limit=2", headers=auth_headers
        )
        assert page1.status_code == 200
        body1 = page1.json()
        assert len(body1["items"]) == 2
        assert body1["nextCursor"] is not None

        page2 = await client.get(
            f"/api/v1/community/feed?limit=2&cursor={body1['nextCursor']}",
            headers=auth_headers,
        )
        assert page2.status_code == 200
        body2 = page2.json()
        assert len(body2["items"]) == 1
        assert body2["items"][0]["id"] == p3.id
        assert body2["nextCursor"] is None


@pytest.mark.api
class TestCommunityStockPosts:
    async def test_get_posts_for_symbol(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "trader@test.com")
        await _seed_post(db_session, other, symbols=("HBL",))
        await _seed_post(db_session, other, symbols=("UBL",))

        resp = await client.get(
            "/api/v1/community/stocks/HBL/posts", headers=auth_headers
        )
        assert resp.status_code == 200
        items = resp.json()["items"]
        assert len(items) == 1
        assert items[0]["symbols"][0]["symbol"] == "HBL"

    async def test_invalid_symbol_rejected(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/community/stocks/FAKE!!/posts", headers=auth_headers
        )
        assert resp.status_code == 400
        assert resp.json()["error"] == "INVALID_STOCK_TAG"


@pytest.mark.api
class TestCommunitySinglePost:
    async def test_get_post(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "single@test.com")
        post = await _seed_post(db_session, other)

        resp = await client.get(
            f"/api/v1/community/posts/{post.id}", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json()["id"] == post.id
        assert resp.json()["content"] == "HBL is looking strong."

    async def test_get_missing_post(self, client: AsyncClient, auth_headers):
        resp = await client.get(
            "/api/v1/community/posts/nonexistent", headers=auth_headers
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "POST_NOT_FOUND"

    async def test_delete_own_post(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)

        resp = await client.delete(
            f"/api/v1/community/posts/{post.id}", headers=auth_headers
        )
        assert resp.status_code == 204

        feed = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert not any(p["id"] == post.id for p in feed.json()["items"])

    async def test_delete_other_users_post(
        self, client: AsyncClient, auth_headers, db_session: AsyncSession
    ):
        other = await _create_user(db_session, "owner@test.com")
        post = await _seed_post(db_session, other)

        resp = await client.delete(
            f"/api/v1/community/posts/{post.id}", headers=auth_headers
        )
        assert resp.status_code == 403
        assert resp.json()["error"] == "FORBIDDEN"


@pytest.mark.api
class TestCommunityLikes:
    async def test_toggle_like(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/like", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == {"postId": post.id, "likedByMe": True, "likeCount": 1}

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/like", headers=auth_headers
        )
        assert resp.status_code == 200
        assert resp.json() == {"postId": post.id, "likedByMe": False, "likeCount": 0}

    async def test_like_missing_post(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts/nope/like", headers=auth_headers
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "POST_NOT_FOUND"

    async def test_liked_by_me_in_feed(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)
        await client.post(f"/api/v1/community/posts/{post.id}/like", headers=auth_headers)

        resp = await client.get("/api/v1/community/feed", headers=auth_headers)
        items = [p for p in resp.json()["items"] if p["id"] == post.id]
        assert items and items[0]["likedByMe"] is True
        assert items[0]["likeCount"] == 1


@pytest.mark.api
class TestCommunityComments:
    async def test_add_comment(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)

        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Nice call!"},
        )
        assert resp.status_code == 201
        data = resp.json()
        assert data["postId"] == post.id
        assert data["content"] == "Nice call!"
        assert data["parentCommentId"] is None
        assert data["user"]["username"] == test_user.username
        assert data["createdAt"].endswith("Z")

        feed = await client.get("/api/v1/community/feed", headers=auth_headers)
        my_post = [p for p in feed.json()["items"] if p["id"] == post.id][0]
        assert my_post["commentCount"] == 1

    async def test_reply_to_top_level_comment(
        self,
        client: AsyncClient,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        post = await _seed_post(db_session, test_user)
        top = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Top-level"},
        )
        comment_id = top.json()["id"]

        reply = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "A reply", "parentCommentId": comment_id},
        )
        assert reply.status_code == 201
        assert reply.json()["parentCommentId"] == comment_id

        comments = await client.get(
            f"/api/v1/community/posts/{post.id}/comments", headers=auth_headers
        )
        assert comments.status_code == 200
        items = comments.json()["items"]
        assert len(items) == 1
        assert items[0]["replies"][0]["content"] == "A reply"

    async def test_reply_depth_capped_at_two(
        self,
        client: AsyncClient,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        post = await _seed_post(db_session, test_user)
        top = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Top-level"},
        )
        reply = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Reply", "parentCommentId": top.json()["id"]},
        )
        deep = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Too deep", "parentCommentId": reply.json()["id"]},
        )
        assert deep.status_code == 422
        assert deep.json()["error"] == "MAX_DEPTH_EXCEEDED"

    async def test_reply_to_missing_comment(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/comments",
            headers=auth_headers,
            json={"content": "Reply", "parentCommentId": "ghost"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "COMMENT_NOT_FOUND"

    async def test_comment_on_missing_post(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/posts/ghost/comments",
            headers=auth_headers,
            json={"content": "Hello"},
        )
        assert resp.status_code == 404


@pytest.mark.api
class TestCommunityReports:
    async def test_report_post(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)
        resp = await client.post(
            "/api/v1/community/reports",
            headers=auth_headers,
            json={"targetType": "POST", "targetId": post.id, "reason": "SPAM"},
        )
        assert resp.status_code == 201
        assert resp.json()["status"] == "PENDING"
        report_id = resp.json()["id"]

        dupe = await client.post(
            "/api/v1/community/reports",
            headers=auth_headers,
            json={"targetType": "POST", "targetId": post.id, "reason": "SPAM"},
        )
        assert dupe.status_code == 201
        assert dupe.json()["id"] == report_id

    async def test_report_missing_target(self, client: AsyncClient, auth_headers):
        resp = await client.post(
            "/api/v1/community/reports",
            headers=auth_headers,
            json={"targetType": "POST", "targetId": "ghost", "reason": "SPAM"},
        )
        assert resp.status_code == 404
        assert resp.json()["error"] == "TARGET_NOT_FOUND"

    async def test_post_auto_flagged_at_threshold(
        self,
        client: AsyncClient,
        auth_headers,
        test_user: User,
        db_session: AsyncSession,
    ):
        from app.core.config import get_settings

        post = await _seed_post(db_session, test_user)
        monkeypatch_threshold = get_settings()
        original = monkeypatch_threshold.COMMUNITY_REPORT_THRESHOLD
        monkeypatch_threshold.COMMUNITY_REPORT_THRESHOLD = 2
        try:
            for i in range(2):
                reporter = await _create_user(db_session, f"reporter{i}@test.com")
                headers = _headers_for(reporter.id)
                resp = await client.post(
                    "/api/v1/community/reports",
                    headers=headers,
                    json={"targetType": "POST", "targetId": post.id, "reason": "SPAM"},
                )
                assert resp.status_code == 201
        finally:
            monkeypatch_threshold.COMMUNITY_REPORT_THRESHOLD = original

        feed = await client.get("/api/v1/community/feed", headers=auth_headers)
        assert not any(p["id"] == post.id for p in feed.json()["items"])

        detail = await client.get(
            f"/api/v1/community/posts/{post.id}", headers=auth_headers
        )
        assert detail.status_code == 200
        assert detail.json()["content"] == "HBL is looking strong."


@pytest.mark.api
class TestCommunityShareLinks:
    async def test_create_and_resolve_share_link(
        self, client: AsyncClient, auth_headers, test_user: User, db_session: AsyncSession
    ):
        post = await _seed_post(db_session, test_user)
        resp = await client.post(
            f"/api/v1/community/posts/{post.id}/share", headers=auth_headers
        )
        assert resp.status_code == 201
        share = resp.json()
        assert share["shortCode"]
        assert share["shortUrl"].endswith(f"/p/{share['shortCode']}")

        # Resolve is public (no auth) and reveals only a teaser
        resolve = await client.get(f"/api/v1/community/share/{share['shortCode']}")
        assert resolve.status_code == 200
        body = resolve.json()
        assert body["postId"] == post.id
        assert body["deepLink"].endswith(f"/post/{post.id}")
        assert body["androidPackage"]
        assert "content" not in body
        assert body["teaser"]["title"]

    async def test_resolve_unknown_share(self, client: AsyncClient):
        resp = await client.get("/api/v1/community/share/doesnotexist")
        assert resp.status_code == 404
        assert resp.json()["error"] == "SHARE_NOT_FOUND"