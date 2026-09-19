import asyncio
import base64
import json
import logging
import re
import secrets
import string
from datetime import datetime

from app.cache.redis_client import redis_client
from app.core.config import get_settings
from app.core.exceptions import CommunityError
from app.models.community import Post
from app.repository.community_repository import CommunityRepository
from app.schemas.community import (
    CommentCreate,
    CommentItem,
    CommentReplyResponse,
    CommentResponse,
    CommentsResponse,
    FeedItem,
    FeedResponse,
    FeedSymbolQuote,
    FeedUser,
    LikeResponse,
    PostCreatedResponse,
    PostCreate,
    ReportResponse,
    ShareLinkResponse,
    ShareResolveResponse,
    to_iso_z,
)
from app.services.stock_service import StockService

logger = logging.getLogger(__name__)

RATE_LIMIT_SECONDS = 30

_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
_REPEATED_CHAR_RE = re.compile(r"(.)\1{5,}")

_PROFANITY_BLOCKLIST = {
    "fuck",
    "shit",
    "bitch",
    "asshole",
    "bastard",
    "dick",
    "cock",
    "pussy",
    "cunt",
    "whore",
    "slut",
    "nigger",
    "nigga",
    "faggot",
    "retard",
    "motherfucker",
    "bullshit",
    "porn",
}


# ── Rate limiting (Redis-backed, fail-open) ─────────────────────────────────
async def acquire_post_slot(user_id: str) -> int:
    """Return 0 if the user may post now, otherwise seconds to wait."""
    try:
        key = f"post_ratelimit:{user_id}"
        acquired = await redis_client.set(key, "1", ex=RATE_LIMIT_SECONDS, nx=True)
        if acquired:
            return 0
        ttl = await redis_client.ttl(key)
        return max(1, int(ttl or RATE_LIMIT_SECONDS))
    except Exception:
        logger.warning("Rate limiter unavailable; allowing post", exc_info=True)
        return 0


# ── Cursor pagination helpers ───────────────────────────────────────────────
def encode_cursor(created_at: datetime, record_id: str) -> str:
    raw = {"createdAt": created_at.isoformat() if created_at else None, "id": record_id}
    return base64.urlsafe_b64encode(json.dumps(raw).encode("utf-8")).decode("utf-8")


def decode_cursor(cursor: str | None) -> tuple[datetime | None, str | None]:
    if not cursor:
        return None, None
    try:
        raw = json.loads(base64.urlsafe_b64decode(cursor.encode("utf-8")).decode("utf-8"))
        created_at = datetime.fromisoformat(raw["createdAt"]) if raw.get("createdAt") else None
        return created_at, raw.get("id")
    except Exception:
        return None, None


# ── Content filter (blocklist + heuristics) ─────────────────────────────────
def content_is_flagged(text: str) -> bool:
    lowered = text.lower()
    for word in _PROFANITY_BLOCKLIST:
        if word in lowered:
            return True

    letters = [ch for ch in text if ch.isalpha()]
    if len(letters) >= 12:
        caps = sum(1 for ch in letters if ch.isupper())
        if caps / len(letters) > 0.6:
            return True

    if _REPEATED_CHAR_RE.search(text):
        return True

    if len(_URL_RE.findall(text)) > 3:
        return True

    return False


class CommunityService:
    def __init__(self, repo: CommunityRepository, stock_service: StockService):
        self.repo = repo
        self.stock_service = stock_service

    def _validate_media_url(self, url: str) -> None:
        """When Cloudinary is configured, the media must belong to our cloud."""
        settings = get_settings()
        cloud = settings.CLOUDINARY_CLOUD_NAME
        if not cloud:
            return  # uploads unconfigured: the schema-level Cloudinary shape check stands
        prefix = f"https://res.cloudinary.com/{cloud}/image/upload/"
        if not url.startswith(prefix):
            raise CommunityError(
                422,
                "INVALID_MEDIA_URL",
                "mediaUrl must reference an image uploaded to Basarat's Cloudinary.",
                field="mediaUrl",
            )

    # ── Create post ───────────────────────────────────────────────────────────
    async def create_post(self, user_id: str, data: PostCreate) -> PostCreatedResponse:
        symbols = []
        for s in data.symbols:
            if s and s not in symbols:
                symbols.append(s)

        retry_after = await acquire_post_slot(user_id)
        if retry_after > 0:
            raise CommunityError(
                429,
                "RATE_LIMITED",
                "Please wait before posting again.",
                extras={"retryAfterSeconds": retry_after},
            )

        if not 1 <= len(symbols) <= 3:
            raise CommunityError(
                400,
                "INVALID_STOCK_TAG",
                "A post must be tagged to between 1 and 3 stocks.",
                field="symbols",
            )

        valid = await self.repo.resolve_valid_symbols(symbols)
        invalid = [s for s in symbols if s not in valid]
        if invalid:
            raise CommunityError(
                400,
                "INVALID_STOCK_TAG",
                f"Symbol '{invalid[0]}' is not a recognized ticker.",
                field="symbols",
            )

        content = data.content.strip()
        if content_is_flagged(content):
            raise CommunityError(
                422,
                "CONTENT_REJECTED",
                "Your post was flagged by our content filter.",
                field="content",
            )

        if data.mediaUrl:
            self._validate_media_url(data.mediaUrl)

        post = await self.repo.create_post(
            user_id=user_id,
            content=content,
            sentiment=data.sentiment,
            media_url=data.mediaUrl,
            symbols=symbols,
        )
        return PostCreatedResponse(
            id=post.id,
            userId=post.user_id,
            content=post.content,
            symbols=list(symbols),
            sentiment=post.sentiment,
            mediaUrl=post.media_url,
            likeCount=post.like_count,
            commentCount=post.comment_count,
            likedByMe=False,
            createdAt=to_iso_z(post.created_at),
        )

    # ── Feed ──────────────────────────────────────────────────────────────────
    async def get_feed(
        self,
        user_id: str,
        cursor: str | None = None,
        limit: int = 20,
        filter: str = "all",
        symbol: str | None = None,
    ) -> FeedResponse:
        # NOTE: 'following' currently resolves to the same universe as 'all'.
        # Follow relationships are intentionally not part of the v1 scope.
        cursor_at, cursor_id = decode_cursor(cursor)
        posts = await self.repo.get_feed(
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            limit=limit + 1,
            symbol=symbol,
        )
        has_more = len(posts) > limit
        page_posts = posts[:limit]
        items = await self._to_feed_items(page_posts, user_id)
        next_cursor = None
        if has_more and page_posts:
            last = page_posts[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return FeedResponse(items=items, nextCursor=next_cursor)

    async def get_stock_posts(
        self,
        user_id: str,
        symbol: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> FeedResponse:
        return await self.get_feed(user_id, cursor=cursor, limit=limit, symbol=symbol.upper())

    async def get_post(self, user_id: str, post_id: str) -> FeedItem:
        post = await self.repo.get_post(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")
        return (await self._to_feed_items([post], user_id))[0]

    async def delete_post(self, user_id: str, post_id: str) -> None:
        post = await self.repo.get_post(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")
        if post.user_id != user_id:
            raise CommunityError(403, "FORBIDDEN", "You can only delete your own posts.")
        await self.repo.set_post_status(post_id, "REMOVED")

    # ── Likes ─────────────────────────────────────────────────────────────────
    async def toggle_like(self, user_id: str, post_id: str) -> LikeResponse:
        post = await self.repo.get_post_for_update(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")

        existing = await self.repo.get_like(post.id, user_id)
        if existing is not None:
            await self.repo.set_like(post.id, user_id, liked=False)
            await self.repo.increment_post_like_count(post.id, -1)
            liked_by_me = False
        else:
            await self.repo.set_like(post.id, user_id, liked=True)
            await self.repo.increment_post_like_count(post.id, +1)
            liked_by_me = True

        await self.repo.db.flush()
        await self.repo.db.refresh(post)
        return LikeResponse(
            postId=post_id,
            likedByMe=liked_by_me,
            likeCount=max(0, post.like_count),
        )

    # ── Comments ──────────────────────────────────────────────────────────────
    async def add_comment(self, user_id: str, post_id: str, data: CommentCreate) -> CommentResponse:
        post = await self.repo.get_post(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")

        content = data.content.strip()
        if content_is_flagged(content):
            raise CommunityError(
                422,
                "CONTENT_REJECTED",
                "Your comment was flagged by our content filter.",
                field="content",
            )

        parent_comment_id = data.parentCommentId
        if parent_comment_id:
            parent = await self.repo.get_comment(parent_comment_id)
            if parent is None or parent.status == "REMOVED":
                raise CommunityError(
                    404,
                    "COMMENT_NOT_FOUND",
                    "The comment you are replying to is unavailable.",
                    field="parentCommentId",
                )
            if parent.parent_comment_id is not None:
                raise CommunityError(
                    422,
                    "MAX_DEPTH_EXCEEDED",
                    "You can only reply to a top-level comment.",
                    field="parentCommentId",
                )
            if parent.post_id != post_id:
                raise CommunityError(
                    400,
                    "INVALID_PARENT_COMMENT",
                    "The parent comment does not belong to this post.",
                    field="parentCommentId",
                )

        comment = await self.repo.create_comment(
            post_id=post_id,
            user_id=user_id,
            content=content,
            parent_comment_id=parent_comment_id,
        )
        await self.repo.increment_post_comment_count(post_id, +1)
        await self.repo.db.flush()

        author = await self.repo.get_user(user_id)
        return CommentResponse(
            id=comment.id,
            postId=comment.post_id,
            user=self._user_summary(author),
            content=comment.content,
            parentCommentId=comment.parent_comment_id,
            likeCount=comment.like_count,
            createdAt=to_iso_z(comment.created_at),
        )

    async def get_comments(
        self,
        post_id: str,
        cursor: str | None = None,
        limit: int = 20,
    ) -> CommentsResponse:
        post = await self.repo.get_post(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")

        cursor_at, cursor_id = decode_cursor(cursor)
        top_level = await self.repo.get_top_level_comments(
            post_id,
            cursor_at=cursor_at,
            cursor_id=cursor_id,
            limit=limit + 1,
        )
        has_more = len(top_level) > limit
        page = top_level[:limit]

        replies = await self.repo.get_replies([c.id for c in page])
        replies_by_parent: dict[str, list] = {}
        for r in replies:
            replies_by_parent.setdefault(r.parent_comment_id, []).append(r)

        items = []
        for c in page:
            reply_items = [
                CommentReplyResponse(
                    id=r.id,
                    user=self._user_summary(r.author),
                    content=r.content,
                    likeCount=r.like_count,
                    createdAt=to_iso_z(r.created_at),
                )
                for r in replies_by_parent.get(c.id, [])
            ]
            items.append(
                CommentItem(
                    id=c.id,
                    user=self._user_summary(c.author),
                    content=c.content,
                    likeCount=c.like_count,
                    createdAt=to_iso_z(c.created_at),
                    replies=reply_items,
                )
            )

        next_cursor = None
        if has_more and page:
            last = page[-1]
            next_cursor = encode_cursor(last.created_at, last.id)
        return CommentsResponse(items=items, nextCursor=next_cursor)

    # ── Reports ───────────────────────────────────────────────────────────────
    async def create_report(self, user_id: str, target_type: str, target_id: str, reason: str) -> ReportResponse:
        existing = await self.repo.get_report(user_id, target_type, target_id)
        if existing is not None:
            return ReportResponse(id=existing.id, status=existing.status)

        if target_type == "POST":
            target = await self.repo.get_post(target_id)
        else:
            target = await self.repo.get_comment(target_id)
        if target is None or target.status == "REMOVED":
            raise CommunityError(404, "TARGET_NOT_FOUND", "The item you are reporting is unavailable.")

        report = await self.repo.create_report(user_id, target_type, target_id, reason)

        threshold = get_settings().COMMUNITY_REPORT_THRESHOLD
        count = await self.repo.count_reports(target_type, target_id)
        if count >= threshold:
            if target_type == "POST":
                await self.repo.set_post_status(target_id, "FLAGGED")
            else:
                await self.repo.set_comment_status(target_id, "REMOVED")

        await self.repo.db.flush()
        return ReportResponse(id=report.id, status=report.status)

    # ── Share links ───────────────────────────────────────────────────────────
    async def create_share_link(self, user_id: str, post_id: str) -> ShareLinkResponse:
        post = await self.repo.get_post(post_id)
        if post is None or post.status == "REMOVED":
            raise CommunityError(404, "POST_NOT_FOUND", "This post is unavailable.")

        short_code = await self._generate_short_code()
        await self.repo.create_share_link(short_code, post_id, user_id)
        await self.repo.db.flush()

        settings = get_settings()
        base_url = settings.SHARE_BASE_URL.rstrip("/")
        return ShareLinkResponse(
            shortUrl=f"{base_url}/p/{short_code}",
            shortCode=short_code,
        )

    async def _generate_short_code(self) -> str:
        alphabet = string.ascii_letters + string.digits
        for _ in range(5):
            code = "".join(secrets.choice(alphabet) for _ in range(8))
            if await self.repo.get_share_link(code) is None:
                return code
        raise CommunityError(503, "SERVICE_UNAVAILABLE", "Could not generate a unique share code.")

    async def resolve_share_link(self, short_code: str) -> ShareResolveResponse:
        link = await self.repo.get_share_link(short_code)
        if link is None:
            raise CommunityError(404, "SHARE_NOT_FOUND", "This share link is invalid or expired.")

        settings = get_settings()
        return ShareResolveResponse(
            postId=link.post_id,
            deepLink=f"{settings.DEEP_LINK_SCHEME}://post/{link.post_id}",
            androidPackage=settings.ANDROID_PACKAGE,
            playStoreUrl=settings.PLAY_STORE_URL,
            teaser={
                "title": f"Someone shared a stock post on {settings.PROJECT_NAME}",
                "description": "Open the app to view this post.",
                "imageUrl": settings.TEASER_IMAGE_URL,
            },
        )

    # ── Serialization helpers ─────────────────────────────────────────────────
    async def _to_feed_items(self, posts: list[Post], viewer_id: str) -> list[FeedItem]:
        if not posts:
            return []
        post_ids = [p.id for p in posts]
        tags = await self.repo.get_tags_for_posts(post_ids)
        liked_ids = await self.repo.get_user_liked_post_ids(post_ids, viewer_id)
        symbol_set = {s for symbols in tags.values() for s in symbols}
        quotes = await self._fetch_quotes(symbol_set)

        items = []
        for p in posts:
            symbol_quotes = [
                FeedSymbolQuote(
                    symbol=s,
                    price=quotes.get(s, {}).get("price", 0.0),
                    changePercent=quotes.get(s, {}).get("changePercent", 0.0),
                )
                for s in tags.get(p.id, [])
            ]
            items.append(
                FeedItem(
                    id=p.id,
                    user=self._user_summary(p.author),
                    content=p.content,
                    symbols=symbol_quotes,
                    sentiment=p.sentiment,
                    mediaUrl=p.media_url,
                    likeCount=p.like_count,
                    commentCount=p.comment_count,
                    likedByMe=p.id in liked_ids,
                    createdAt=to_iso_z(p.created_at),
                )
            )
        return items

    async def _fetch_quotes(self, symbols: set[str]) -> dict[str, dict]:
        if not symbols:
            return {}
        try:
            rows = await asyncio.to_thread(self.stock_service.get_quote_batch, list(symbols))
        except Exception:
            logger.warning("Live quote lookup failed; using zero quotes", exc_info=True)
            rows = []
        out: dict[str, dict] = {}
        for row in rows or []:
            symbol = str(row.get("symbol", "")).upper()
            if not symbol:
                continue
            out[symbol] = {
                "price": float(row.get("current") or 0.0),
                "changePercent": float(row.get("change_pct") or 0.0),
            }
        return out

    @staticmethod
    def _user_summary(user) -> FeedUser:
        if user is None:
            return FeedUser(id="", username="", avatarUrl=None)
        return FeedUser(id=user.id, username=user.username, avatarUrl=user.avatar_url)