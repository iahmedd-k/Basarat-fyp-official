package com.fyp.basarattradeinvest.community

import com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotificationList
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityPostList
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.domain.model.community.CommunityReport
import com.fyp.basarattradeinvest.domain.model.community.CommunityUnreadCount
import com.fyp.basarattradeinvest.domain.model.community.ModerationAction
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.fyp.basarattradeinvest.domain.usecase.community.CreateCommunityPostUseCase
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test

class CreateCommunityPostUseCaseTest {

    private class FakeCommunityRepository : CommunityRepository {
        var lastContent: String? = null
        var lastPostType: String? = null
        var lastStockSymbol: String? = null
        var shouldFail: Boolean = false

        override suspend fun createPost(
            content: String,
            postType: String,
            stockSymbol: String?,
            imageBytes: ByteArray?,
            imageFileName: String?,
            imageMimeType: String?
        ): Result<CommunityPost> {
            if (shouldFail) {
                return Result.failure(RuntimeException("Network error"))
            }
            lastContent = content
            lastPostType = postType
            lastStockSymbol = stockSymbol
            return Result.success(
                CommunityPost(
                    id = "post-101",
                    authorId = "user-1",
                    authorUsername = "investor_pro",
                    authorFullName = "Investor Pro",
                    authorAvatarUrl = null,
                    content = content,
                    postType = postType,
                    stockSymbol = stockSymbol,
                    stockName = if (stockSymbol != null) "$stockSymbol Limited" else null,
                    imageUrl = null,
                    likeCount = 0,
                    commentCount = 0,
                    reportCount = 0,
                    status = "ACTIVE",
                    removedReason = null,
                    likedByMe = false,
                    createdAt = "2026-09-24T18:00:00Z",
                    updatedAt = "2026-09-24T18:00:00Z"
                )
            )
        }

        override suspend fun getCommunityFeed(
            stockSymbol: String?,
            postType: String?,
            mine: Boolean?,
            following: Boolean?,
            cursor: String?,
            limit: Int?
        ): Result<CommunityPostList> = Result.success(CommunityPostList(emptyList(), null, false))

        override suspend fun getMyProfile(): Result<CommunityProfile> = TODO()
        override suspend fun getUserProfile(userId: String): Result<CommunityProfile> = TODO()
        override suspend fun getMyPosts(cursor: String?, limit: Int?): Result<CommunityPostList> = TODO()
        override suspend fun getUserPosts(userId: String, cursor: String?, limit: Int?): Result<CommunityPostList> = TODO()
        override suspend fun getFollowers(userId: String, cursor: String?, limit: Int?): Result<CommunityFollowList> = TODO()
        override suspend fun getFollowing(userId: String, cursor: String?, limit: Int?): Result<CommunityFollowList> = TODO()
        override suspend fun getCommunityNotifications(page: Int?, limit: Int?, unreadOnly: Boolean?): Result<CommunityNotificationList> = TODO()
        override suspend fun getUnreadNotificationCount(): Result<CommunityUnreadCount> = TODO()
        override suspend fun markNotificationAsRead(notificationId: String): Result<Unit> = TODO()
        override suspend fun markAllNotificationsAsRead(): Result<Unit> = TODO()
        override suspend fun getAdminReports(status: String?, postId: String?, commentId: String?, limit: Int, offset: Int): Result<List<CommunityReport>> = TODO()
        override suspend fun updateReportStatus(reportId: String, status: String): Result<Unit> = TODO()
        override suspend fun getAdminPost(postId: String): Result<CommunityPost> = TODO()
        override suspend fun deleteAdminPost(postId: String): Result<Unit> = TODO()
        override suspend fun restoreAdminPost(postId: String): Result<Unit> = TODO()
        override suspend fun removeAdminPost(postId: String): Result<Unit> = TODO()
        override suspend fun deleteAdminComment(commentId: String): Result<Unit> = TODO()
        override suspend fun getModerationActions(postId: String?, commentId: String?, limit: Int): Result<List<ModerationAction>> = TODO()
        override suspend fun likePost(postId: String): Result<Unit> = Result.success(Unit)
        override suspend fun unlikePost(postId: String): Result<Unit> = Result.success(Unit)
        override suspend fun getComments(postId: String, cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList> =
            Result.success(com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList(emptyList(), null, false))
        override suspend fun createComment(postId: String, content: String, parentCommentId: String?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityComment> =
            Result.failure(NotImplementedError())
    }

    private lateinit var fakeRepository: FakeCommunityRepository
    private lateinit var useCase: CreateCommunityPostUseCase

    @Before
    fun setUp() {
        fakeRepository = FakeCommunityRepository()
        useCase = CreateCommunityPostUseCase(fakeRepository)
    }

    @Test
    fun `invoke with blank content returns failure`() = runBlocking {
        val result = useCase(
            content = "   ",
            postType = "GENERAL_MARKET",
            stockSymbol = null,
            imageBytes = null,
            imageFileName = null
        )

        assertTrue(result.isFailure)
        assertEquals("Post content cannot be empty.", result.exceptionOrNull()?.message)
    }

    @Test
    fun `invoke with content exceeding 5000 chars returns failure`() = runBlocking {
        val longContent = "a".repeat(5001)
        val result = useCase(
            content = longContent,
            postType = "GENERAL_MARKET",
            stockSymbol = null,
            imageBytes = null,
            imageFileName = null
        )

        assertTrue(result.isFailure)
        assertEquals("Post content exceeds 5,000 characters limit.", result.exceptionOrNull()?.message)
    }

    @Test
    fun `invoke with STOCK post type and blank symbol returns failure`() = runBlocking {
        val result = useCase(
            content = "Bullish on this stock!",
            postType = "STOCK",
            stockSymbol = "  ",
            imageBytes = null,
            imageFileName = null
        )

        assertTrue(result.isFailure)
        assertEquals("Please specify a stock ticker for Stock Idea posts.", result.exceptionOrNull()?.message)
    }

    @Test
    fun `invoke with valid parameters delegates to repository`() = runBlocking {
        val result = useCase(
            content = "  Strong breakout on LUCK!  ",
            postType = "STOCK",
            stockSymbol = "luck",
            imageBytes = null,
            imageFileName = null
        )

        assertTrue(result.isSuccess)
        val post = result.getOrNull()
        assertEquals("post-101", post?.id)
        assertEquals("Strong breakout on LUCK!", fakeRepository.lastContent)
        assertEquals("STOCK", fakeRepository.lastPostType)
        assertEquals("LUCK", fakeRepository.lastStockSymbol)
    }

    @Test
    fun `invoke with GENERAL_MARKET clears stock symbol`() = runBlocking {
        val result = useCase(
            content = "Market rally today across the board",
            postType = "GENERAL_MARKET",
            stockSymbol = "ignored",
            imageBytes = null,
            imageFileName = null
        )

        assertTrue(result.isSuccess)
        assertEquals(null, fakeRepository.lastStockSymbol)
        assertEquals("GENERAL_MARKET", fakeRepository.lastPostType)
    }
}
