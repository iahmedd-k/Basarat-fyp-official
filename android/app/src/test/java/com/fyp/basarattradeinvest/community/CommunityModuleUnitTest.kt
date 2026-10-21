package com.fyp.basarattradeinvest.community

import com.fyp.basarattradeinvest.data.mapper.CommunityDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.CommunityApiService
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityFollowListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityNotificationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityNotificationsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityProfileResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityUnreadCountResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityUserSummaryDto
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.usecase.community.GetCommunityNotificationsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetFollowersUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetFollowingUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetMyCommunityProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetMyPostsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUnreadCommunityNotificationCountUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUserCommunityProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetUserPostsUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.MarkAllCommunityNotificationsReadUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.MarkCommunityNotificationReadUseCase
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.ResponseBody.Companion.toResponseBody
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Response

class CommunityModuleUnitTest {

    private class FakeCommunityApiService : CommunityApiService {
        var shouldFail: Boolean = false

        override suspend fun getFollowers(userId: String, cursor: String?, limit: Int?): Response<CommunityFollowListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityFollowListResponseDto(
                    users = listOf(
                        CommunityUserSummaryDto(id = "u-1", username = "trader_one", fullName = "Trader One", avatarUrl = null)
                    ),
                    cursor = "next_cursor_123",
                    hasMore = true
                )
            )
        }

        override suspend fun getFollowing(userId: String, cursor: String?, limit: Int?): Response<CommunityFollowListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityFollowListResponseDto(
                    users = listOf(
                        CommunityUserSummaryDto(id = "u-2", username = "trader_two", fullName = "Trader Two", avatarUrl = null)
                    ),
                    cursor = null,
                    hasMore = false
                )
            )
        }

        override suspend fun getMyCommunityProfile(): Response<CommunityProfileResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityProfileResponseDto(
                    id = "me-123",
                    username = "my_user",
                    fullName = "My Name",
                    avatarUrl = null,
                    followersCount = 50,
                    followingCount = 20,
                    publishedPostCount = 5,
                    isFollowing = false,
                    isOwnProfile = true
                )
            )
        }

        override suspend fun getMyPosts(cursor: String?, limit: Int?): Response<CommunityPostListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityPostListResponseDto(
                    posts = listOf(
                        CommunityPostResponseDto(
                            id = "p-1",
                            authorId = "me-123",
                            postType = "STOCK",
                            stockSymbol = "LUCK",
                            content = "Buying Lucky Cement on support",
                            imageUrl = null,
                            likeCount = 10,
                            commentCount = 2,
                            reportCount = 0,
                            status = "PUBLISHED",
                            removedReason = null,
                            likedByMe = true,
                            createdAt = "2026-09-24T10:00:00Z",
                            updatedAt = "2026-09-24T10:00:00Z"
                        )
                    ),
                    cursor = null,
                    hasMore = false
                )
            )
        }

        override suspend fun getUserProfile(userId: String): Response<CommunityProfileResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityProfileResponseDto(
                    id = userId,
                    username = "other_user",
                    fullName = "Other Trader",
                    avatarUrl = null,
                    followersCount = 100,
                    followingCount = 80,
                    publishedPostCount = 30,
                    isFollowing = true,
                    isOwnProfile = false
                )
            )
        }

        override suspend fun getUserPosts(userId: String, cursor: String?, limit: Int?): Response<CommunityPostListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityPostListResponseDto(
                    posts = listOf(
                        CommunityPostResponseDto(
                            id = "p-2",
                            authorId = userId,
                            postType = "GENERAL_MARKET",
                            stockSymbol = null,
                            content = "Market rally today",
                            imageUrl = null,
                            likeCount = 15,
                            commentCount = 4,
                            reportCount = 0,
                            status = "PUBLISHED",
                            removedReason = null,
                            likedByMe = false,
                            createdAt = "2026-09-24T09:00:00Z",
                            updatedAt = "2026-09-24T09:00:00Z"
                        )
                    ),
                    cursor = null,
                    hasMore = false
                )
            )
        }

        override suspend fun getCommunityNotifications(
            page: Int?,
            limit: Int?,
            unreadOnly: Boolean?
        ): Response<CommunityNotificationsListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            val notifs = listOf(
                CommunityNotificationResponseDto(
                    id = "n-1",
                    recipientId = "me-123",
                    actorId = "u-1",
                    actorUsername = "trader_one",
                    postId = "p-1",
                    commentId = null,
                    type = "POST_LIKED",
                    title = "Post Liked",
                    message = "trader_one liked your post",
                    isRead = false,
                    createdAt = "2026-09-24T11:00:00Z"
                )
            )
            return Response.success(
                CommunityNotificationsListResponseDto(
                    notifications = notifs,
                    total = 1,
                    page = 1,
                    limit = 20,
                    hasMore = false
                )
            )
        }

        override suspend fun getUnreadNotificationCount(): Response<CommunityUnreadCountResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityUnreadCountResponseDto(
                    count = 4,
                    unreadCount = null
                )
            )
        }

        override suspend fun markNotificationAsRead(notificationId: String): Response<Unit> {
            if (shouldFail) return Response.error(404, "{\"detail\":\"Not Found\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun markAllNotificationsAsRead(): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun getAdminReports(
            status: String?,
            postId: String?,
            commentId: String?,
            limit: Int?,
            offset: Int?
        ): Response<com.google.gson.JsonElement> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(com.google.gson.JsonArray())
        }

        override suspend fun updateReportStatus(
            reportId: String,
            body: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportStatusUpdateRequest
        ): Response<com.google.gson.JsonElement> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(com.google.gson.JsonObject())
        }

        override suspend fun getAdminPost(postId: String): Response<CommunityPostResponseDto> {
            if (shouldFail) return Response.error(404, "{\"detail\":\"Not Found\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityPostResponseDto(
                    id = postId,
                    authorId = "author-1",
                    postType = "GENERAL",
                    stockSymbol = null,
                    content = "Admin post",
                    imageUrl = null,
                    likeCount = 0,
                    commentCount = 0,
                    reportCount = 0,
                    status = "PUBLISHED",
                    removedReason = null,
                    likedByMe = false,
                    createdAt = "2026-09-24T10:00:00Z",
                    updatedAt = "2026-09-24T10:00:00Z"
                )
            )
        }

        override suspend fun deleteAdminPost(postId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun restoreAdminPost(postId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun removeAdminPost(postId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun deleteAdminComment(commentId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun getModerationActions(
            postId: String?,
            commentId: String?,
            limit: Int?
        ): Response<com.google.gson.JsonElement> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(com.google.gson.JsonArray())
        }

        override suspend fun createPost(
            content: okhttp3.RequestBody,
            postType: okhttp3.RequestBody,
            stockSymbol: okhttp3.RequestBody?,
            image: okhttp3.MultipartBody.Part?
        ): Response<CommunityPostResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityPostResponseDto(
                    id = "p-created-1",
                    authorId = "me-123",
                    postType = "STOCK",
                    stockSymbol = "LUCK",
                    content = "Created post",
                    imageUrl = null,
                    likeCount = 0,
                    commentCount = 0,
                    reportCount = 0,
                    status = "PUBLISHED",
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
        ): Response<CommunityPostListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                CommunityPostListResponseDto(
                    posts = emptyList(),
                    cursor = null,
                    hasMore = false
                )
            )
        }

        override suspend fun likePost(postId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun unlikePost(postId: String): Response<Unit> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(Unit)
        }

        override suspend fun getComments(postId: String, cursor: String?, limit: Int?): Response<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentListResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentListResponseDto(
                    comments = emptyList(),
                    cursor = null,
                    hasMore = false
                )
            )
        }

        override suspend fun createComment(
            postId: String,
            body: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentCreateDto
        ): Response<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentResponseDto> {
            if (shouldFail) return Response.error(500, "{\"detail\":\"Internal Error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            return Response.success(
                com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentResponseDto(
                    id = "c-1",
                    postId = postId,
                    authorId = "me-123",
                    authorUsername = "my_user",
                    authorFullName = "My Name",
                    authorAvatarUrl = null,
                    parentCommentId = body.parentCommentId,
                    content = body.content,
                    status = "PUBLISHED",
                    replyCount = 0,
                    createdAt = "2026-09-24T18:00:00Z",
                    updatedAt = "2026-09-24T18:00:00Z"
                )
            )
        }
    }

    private lateinit var fakeApi: FakeCommunityApiService
    private lateinit var repository: CommunityRepositoryImpl

    @Before
    fun setUp() {
        fakeApi = FakeCommunityApiService()
        repository = CommunityRepositoryImpl(fakeApi)
    }

    // ───────────────────────────────
    // DTO Mapper Tests
    // ───────────────────────────────

    @Test
    fun testCommunityDtoMapper_mapsProfileCorrectly() {
        val dto = CommunityProfileResponseDto(
            id = "user-abc",
            username = "tariq_equity",
            fullName = "Tariq Mahmood",
            avatarUrl = "https://example.com/avatar.jpg",
            followersCount = 1420,
            followingCount = 88,
            publishedPostCount = 34,
            isFollowing = true,
            isOwnProfile = false
        )
        val domain = CommunityDtoMapper.mapProfileDtoToDomain(dto)

        assertEquals("user-abc", domain.id)
        assertEquals("tariq_equity", domain.username)
        assertEquals("Tariq Mahmood", domain.fullName)
        assertEquals("Tariq Mahmood", domain.displayName)
        assertEquals(1420, domain.followersCount)
        assertEquals(88, domain.followingCount)
        assertEquals(34, domain.publishedPostCount)
        assertTrue(domain.isFollowing)
        assertFalse(domain.isOwnProfile)
    }

    @Test
    fun testCommunityDtoMapper_mapsUserSummaryCorrectly() {
        val dto = CommunityUserSummaryDto(
            id = "u-99",
            username = "karachi_trader",
            fullName = null,
            avatarUrl = null
        )
        val domain = CommunityDtoMapper.mapUserSummaryDtoToDomain(dto)

        assertEquals("u-99", domain.id)
        assertEquals("karachi_trader", domain.username)
        assertEquals("@karachi_trader", domain.displayName)
    }

    @Test
    fun testCommunityDtoMapper_mapsFollowListCorrectly() {
        val dto = CommunityFollowListResponseDto(
            users = listOf(
                CommunityUserSummaryDto("u-1", "user1", "User One", null)
            ),
            cursor = "cursor_token_456",
            hasMore = true
        )
        val domain = CommunityDtoMapper.mapFollowListDtoToDomain(dto)

        assertEquals(1, domain.users.size)
        assertEquals("cursor_token_456", domain.cursor)
        assertTrue(domain.hasMore)
    }

    @Test
    fun testCommunityDtoMapper_mapsPostCorrectly() {
        val dto = CommunityPostResponseDto(
            id = "post-99",
            authorId = "author-88",
            postType = "STOCK",
            stockSymbol = "ENGRO",
            content = "Engro Corp long-term dividend thesis",
            imageUrl = null,
            likeCount = 42,
            commentCount = 7,
            reportCount = 0,
            status = "PUBLISHED",
            removedReason = null,
            likedByMe = true,
            createdAt = "2026-09-24T00:00:00Z",
            updatedAt = "2026-09-24T00:00:00Z"
        )
        val domain = CommunityDtoMapper.mapPostDtoToDomain(dto)

        assertEquals("post-99", domain.id)
        assertTrue(domain.isStockPost)
        assertEquals("ENGRO", domain.stockSymbol)
        assertEquals(42, domain.likeCount)
        assertEquals(7, domain.commentCount)
        assertTrue(domain.likedByMe)
    }

    @Test
    fun testCommunityDtoMapper_mapsNotificationAndUnreadCount() {
        val notifDto = CommunityNotificationResponseDto(
            id = "notif-1",
            recipientId = "rec-1",
            actorId = "act-1",
            actorUsername = "ali_investor",
            postId = "post-1",
            commentId = null,
            type = "POST_LIKED",
            title = "New Like",
            message = "ali_investor liked your post",
            isRead = false,
            createdAt = "2026-09-24T10:00:00Z"
        )
        val notifDomain = CommunityDtoMapper.mapNotificationDtoToDomain(notifDto)
        assertEquals("notif-1", notifDomain.id)
        assertEquals("ali_investor", notifDomain.actorUsername)
        assertFalse(notifDomain.isRead)

        val unreadDto1 = CommunityUnreadCountResponseDto(count = 5, unreadCount = null)
        assertEquals(5, CommunityDtoMapper.mapUnreadCountDtoToDomain(unreadDto1).unreadCount)

        val unreadDto2 = CommunityUnreadCountResponseDto(count = null, unreadCount = 8)
        assertEquals(8, CommunityDtoMapper.mapUnreadCountDtoToDomain(unreadDto2).unreadCount)
    }

    // ───────────────────────────────
    // Repository Tests
    // ───────────────────────────────

    @Test
    fun testRepository_getMyProfile_success() = runBlocking {
        fakeApi.shouldFail = false
        val result = repository.getMyProfile()

        assertTrue(result.isSuccess)
        val profile = result.getOrNull()
        assertNotNull(profile)
        assertEquals("me-123", profile?.id)
        assertEquals("my_user", profile?.username)
        assertTrue(profile?.isOwnProfile == true)
    }

    @Test
    fun testRepository_getUserProfile_success() = runBlocking {
        fakeApi.shouldFail = false
        val result = repository.getUserProfile("user-xyz")

        assertTrue(result.isSuccess)
        val profile = result.getOrNull()
        assertNotNull(profile)
        assertEquals("user-xyz", profile?.id)
        assertEquals("other_user", profile?.username)
        assertTrue(profile?.isFollowing == true)
    }

    @Test
    fun testRepository_postsAndFollowers_success() = runBlocking {
        fakeApi.shouldFail = false

        val myPosts = repository.getMyPosts()
        assertTrue(myPosts.isSuccess)
        assertEquals(1, myPosts.getOrNull()?.posts?.size)
        assertEquals("LUCK", myPosts.getOrNull()?.posts?.first()?.stockSymbol)

        val userPosts = repository.getUserPosts("user-xyz")
        assertTrue(userPosts.isSuccess)
        assertEquals(1, userPosts.getOrNull()?.posts?.size)

        val followers = repository.getFollowers("user-xyz")
        assertTrue(followers.isSuccess)
        assertEquals(1, followers.getOrNull()?.users?.size)
        assertEquals("trader_one", followers.getOrNull()?.users?.first()?.username)

        val following = repository.getFollowing("user-xyz")
        assertTrue(following.isSuccess)
        assertEquals(1, following.getOrNull()?.users?.size)
        assertEquals("trader_two", following.getOrNull()?.users?.first()?.username)
    }

    @Test
    fun testRepository_notificationsAndUnreadCount_success() = runBlocking {
        fakeApi.shouldFail = false

        val notifs = repository.getCommunityNotifications()
        assertTrue(notifs.isSuccess)
        assertEquals(1, notifs.getOrNull()?.notifications?.size)
        assertEquals("POST_LIKED", notifs.getOrNull()?.notifications?.first()?.type)

        val unread = repository.getUnreadNotificationCount()
        assertTrue(unread.isSuccess)
        assertEquals(4, unread.getOrNull()?.unreadCount)

        val markRead = repository.markNotificationAsRead("n-1")
        assertTrue(markRead.isSuccess)

        val markAllRead = repository.markAllNotificationsAsRead()
        assertTrue(markAllRead.isSuccess)
    }

    @Test
    fun testRepository_handlesFailure_whenApiFails() = runBlocking {
        fakeApi.shouldFail = true

        val myProfile = repository.getMyProfile()
        assertTrue(myProfile.isFailure)

        val userProfile = repository.getUserProfile("test-id")
        assertTrue(userProfile.isFailure)

        val myPosts = repository.getMyPosts()
        assertTrue(myPosts.isFailure)

        val followers = repository.getFollowers("test-id")
        assertTrue(followers.isFailure)

        val notifs = repository.getCommunityNotifications()
        assertTrue(notifs.isFailure)

        val markRead = repository.markNotificationAsRead("n-fail")
        assertTrue(markRead.isFailure)
    }

    // ───────────────────────────────
    // Use Cases Validation Tests
    // ───────────────────────────────

    @Test
    fun testUseCases_executeAndValidateParams() = runBlocking {
        fakeApi.shouldFail = false

        val getMyProfileUseCase = GetMyCommunityProfileUseCase(repository)
        val getUserProfileUseCase = GetUserCommunityProfileUseCase(repository)
        val getMyPostsUseCase = GetMyPostsUseCase(repository)
        val getUserPostsUseCase = GetUserPostsUseCase(repository)
        val getFollowersUseCase = GetFollowersUseCase(repository)
        val getFollowingUseCase = GetFollowingUseCase(repository)
        val getNotifsUseCase = GetCommunityNotificationsUseCase(repository)
        val getUnreadUseCase = GetUnreadCommunityNotificationCountUseCase(repository)
        val markReadUseCase = MarkCommunityNotificationReadUseCase(repository)
        val markAllReadUseCase = MarkAllCommunityNotificationsReadUseCase(repository)

        assertTrue(getMyProfileUseCase().isSuccess)
        assertTrue(getUserProfileUseCase("valid-user").isSuccess)
        assertTrue(getMyPostsUseCase().isSuccess)
        assertTrue(getUserPostsUseCase("valid-user").isSuccess)
        assertTrue(getFollowersUseCase("valid-user").isSuccess)
        assertTrue(getFollowingUseCase("valid-user").isSuccess)
        assertTrue(getNotifsUseCase().isSuccess)
        assertTrue(getUnreadUseCase().isSuccess)
        assertTrue(markReadUseCase("valid-notif-id").isSuccess)
        assertTrue(markAllReadUseCase().isSuccess)

        // Validation exceptions for blank arguments
        try {
            getUserProfileUseCase("")
            org.junit.Assert.fail("Expected exception for blank userId")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message?.contains("User ID") == true)
        }

        try {
            markReadUseCase("")
            org.junit.Assert.fail("Expected exception for blank notificationId")
        } catch (e: IllegalArgumentException) {
            assertTrue(e.message?.contains("Notification ID") == true)
        }
    }
}
