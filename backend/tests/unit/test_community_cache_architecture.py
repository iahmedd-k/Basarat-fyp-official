"""Unit tests verifying Redis read-through caching and mutation invalidations for the Community module."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.community_cache_service import CommunityCacheService
from app.core.redis import cache_get, cache_set, cache_invalidate, cache_invalidate_pattern


@pytest.mark.asyncio
async def test_community_cache_service_key_generators():
    """Verify standard deterministic key patterns."""
    assert CommunityCacheService.post_detail_key("p1", "u1") == "community:post_detail:p1:u1"
    assert "market" in CommunityCacheService.market_posts_key(None, 20, "u1")
    assert "stock:TRG" in CommunityCacheService.stock_posts_key("trg", None, 20, "u1")
    assert "profile:u2:u1" in CommunityCacheService.user_profile_key("u2", "u1")
    assert "follow_status:u1:u2" in CommunityCacheService.follow_status_key("u1", "u2")
    assert "unread_count:u1" in CommunityCacheService.unread_count_key("u1")
    assert "comments:p1:first:20" in CommunityCacheService.post_comments_key("p1", None, 20)
    assert "replies:c1:20" in CommunityCacheService.comment_replies_key("c1", 20)


@pytest.mark.asyncio
async def test_community_cache_invalidation_patterns():
    """Verify cache invalidations trigger expected patterns."""
    with patch("app.services.community_cache_service.cache_invalidate_pattern", new_callable=AsyncMock) as mock_pattern, \
         patch("app.services.community_cache_service.cache_invalidate", new_callable=AsyncMock) as mock_inv:
        
        # 1. Post mutation
        await CommunityCacheService.invalidate_post_mutations("p1", "author1", "TRG")
        assert mock_pattern.call_count >= 5

        # 2. Comment mutation
        await CommunityCacheService.invalidate_comment_mutations("p1", "c1")
        assert mock_pattern.call_count >= 7

        # 3. Follow mutation
        await CommunityCacheService.invalidate_follow_mutations("f1", "f2")
        mock_inv.assert_called_with("community:follow_status:f1:f2")

        # 4. Notification mutation
        await CommunityCacheService.invalidate_notification_mutations("u1")
        mock_inv.assert_called_with("community:unread_count:u1")
