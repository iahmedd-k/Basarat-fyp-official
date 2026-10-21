package com.fyp.basarattradeinvest.community

import com.fyp.basarattradeinvest.data.repository.CommunityFeedCache
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.google.gson.Gson
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotEquals
import org.junit.Test

class CommunityFeedCacheTest {

    private val gson = Gson()

    private val profile = CommunityProfile(
        id = "user-1",
        username = "TraderOne",
        fullName = "Trader One",
        avatarUrl = null,
        followersCount = 3,
        followingCount = 4,
        publishedPostCount = 5,
        isFollowing = false,
        isOwnProfile = true
    )

    private val post = CommunityPost(
        id = "post-1",
        authorId = "user-1",
        postType = "STOCK",
        stockSymbol = "SYS",
        content = "Watching the breakout",
        imageUrl = null,
        likeCount = 7,
        commentCount = 2,
        reportCount = 0,
        status = "PUBLISHED",
        removedReason = null,
        likedByMe = true,
        createdAt = "2026-10-04T09:12:00",
        updatedAt = "2026-10-04T09:12:00",
        authorUsername = "TraderOne",
        authorFullName = "Trader One",
        authorAvatarUrl = null,
        stockName = "Systems Limited"
    )

    @Test
    fun `snapshot survives the gson round trip with every field intact`() {
        val snapshot = CommunityFeedCache.Snapshot(
            profile = profile,
            posts = listOf(post),
            cursor = "next-page-cursor",
            hasMore = true,
            savedAt = 1_730_000_000_000L
        )

        val restored = gson.fromJson(gson.toJson(snapshot), CommunityFeedCache.Snapshot::class.java)

        assertEquals(snapshot, restored)
        assertEquals("Trader One", restored.profile.displayName)
        assertEquals(7, restored.posts.first().likeCount)
        assertEquals("next-page-cursor", restored.cursor)
    }

    @Test
    fun `snapshot survives a round trip when optional fields are absent`() {
        val json = """
            {"profile":{"id":"user-1","username":"TraderOne","followersCount":3,"followingCount":4,
            "publishedPostCount":5,"isFollowing":false,"isOwnProfile":true},
            "posts":[{"id":"post-1","authorId":"user-1","postType":"GENERAL","content":"hi",
            "likeCount":1,"commentCount":0,"reportCount":0,"status":"PUBLISHED","likedByMe":false,
            "createdAt":"2026-10-04T09:12:00","updatedAt":"2026-10-04T09:12:00","authorUsername":"TraderOne"}],
            "hasMore":false,"savedAt":1730000000000}
        """.trimIndent()

        val restored = gson.fromJson(json, CommunityFeedCache.Snapshot::class.java)!!

        assertEquals(1, restored.posts.size)
        assertEquals("@TraderOne", restored.posts.first().authorDisplayName)
        assertEquals(null, restored.cursor)
        assertEquals(null, restored.profile.fullName)
    }

    @Test
    fun `keys isolate account, feed mode and filters so a snapshot cannot surface elsewhere`() {
        val self = CommunityFeedCache.keyFor(null, "COMMUNITY_FEED", null, null)
        assertEquals(self, CommunityFeedCache.keyFor(null, "COMMUNITY_FEED", null, null))

        assertNotEquals(self, CommunityFeedCache.keyFor("user-2", "COMMUNITY_FEED", null, null))
        assertNotEquals(self, CommunityFeedCache.keyFor(null, "MY_POSTS", null, null))
        assertNotEquals(self, CommunityFeedCache.keyFor(null, "COMMUNITY_FEED", "STOCK", null))
        assertNotEquals(self, CommunityFeedCache.keyFor(null, "COMMUNITY_FEED", null, "SYS"))
    }
}
