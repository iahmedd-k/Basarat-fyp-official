package com.fyp.basarattradeinvest.community

import com.fyp.basarattradeinvest.data.mapper.CommunityDtoMapper
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportStatusUpdateRequest
import com.fyp.basarattradeinvest.data.remote.dto.community.ModerationActionDto
import com.fyp.basarattradeinvest.domain.model.community.CommunityComment
import com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityReport
import com.fyp.basarattradeinvest.domain.model.community.ModerationAction
import com.fyp.basarattradeinvest.domain.model.community.ModerationPostStatus
import com.fyp.basarattradeinvest.domain.model.community.ReportStatusEnum
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.google.gson.Gson
import kotlinx.coroutines.runBlocking
import org.junit.Assert.assertEquals
import org.junit.Assert.assertFalse
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Test

class AdminCommunityUnitTest {

    private val gson = Gson()

    // ─────────────────────────────────────────
    // 1. DTO & Enums Serialization Tests
    // ─────────────────────────────────────────

    @Test
    fun testReportDtoParsing() {
        val json = """
            {
                "id": "rep_12345",
                "post_id": "post_999",
                "comment_id": null,
                "reporter_id": "usr_888",
                "reporter_username": "diligent_trader",
                "reason": "Spam and market manipulation",
                "status": "PENDING",
                "target_content": "Guaranteed 1000% returns tomorrow buy now!",
                "created_at": "2026-09-24T10:00:00Z",
                "updated_at": null
            }
        """.trimIndent()

        val dto = gson.fromJson(json, CommunityReportDto::class.java)
        assertEquals("rep_12345", dto.id)
        assertEquals("post_999", dto.postId)
        assertEquals("usr_888", dto.reporterId)
        assertEquals("diligent_trader", dto.reporterUsername)
        assertEquals("PENDING", dto.status)
        assertEquals("Spam and market manipulation", dto.reason)

        val domain = CommunityDtoMapper.mapReportDtoToDomain(dto)
        assertEquals(ReportStatusEnum.PENDING, domain.status)
        assertTrue(domain.isPostReport)
        assertFalse(domain.isCommentReport)
        assertEquals("Post", domain.targetTypeLabel)
    }

    @Test
    fun testReportCommentDtoParsing() {
        val json = """
            {
                "id": "rep_555",
                "post_id": null,
                "comment_id": "comm_777",
                "user_id": "usr_222",
                "reason": "Offensive language",
                "status": "REVIEWED",
                "created_at": "2026-09-24T12:00:00Z"
            }
        """.trimIndent()

        val dto = gson.fromJson(json, CommunityReportDto::class.java)
        val domain = CommunityDtoMapper.mapReportDtoToDomain(dto)
        assertEquals("rep_555", domain.id)
        assertEquals("comm_777", domain.commentId)
        assertEquals("usr_222", domain.reporterId)
        assertEquals(ReportStatusEnum.REVIEWED, domain.status)
        assertFalse(domain.isPostReport)
        assertTrue(domain.isCommentReport)
        assertEquals("Comment", domain.targetTypeLabel)
    }

    @Test
    fun testModerationActionDtoParsing() {
        val json = """
            {
                "id": "act_991",
                "action": "REMOVE_POST",
                "moderator_id": "usr_admin",
                "moderator_username": "super_mod",
                "post_id": "post_999",
                "reason": "Automated violation trigger",
                "created_at": "2026-09-24T14:30:00Z"
            }
        """.trimIndent()

        val dto = gson.fromJson(json, ModerationActionDto::class.java)
        assertEquals("act_991", dto.id)
        assertEquals("REMOVE_POST", dto.effectiveAction)
        assertEquals("super_mod", dto.moderatorUsername)

        val domain = CommunityDtoMapper.mapModerationActionDtoToDomain(dto)
        assertEquals("REMOVE_POST", domain.action)
        assertEquals("super_mod", domain.moderatorUsername)
        assertEquals("post_999", domain.postId)
        assertEquals("Automated violation trigger", domain.reason)
    }

    @Test
    fun testReportStatusUpdateRequestBody() {
        val body = CommunityReportStatusUpdateRequest(status = "DISMISSED")
        val json = gson.toJson(body)
        assertTrue(json.contains("\"status\":\"DISMISSED\""))
    }

    @Test
    fun testEnumsFromValue() {
        assertEquals(ReportStatusEnum.PENDING, ReportStatusEnum.fromValue("PENDING"))
        assertEquals(ReportStatusEnum.DISMISSED, ReportStatusEnum.fromValue("dismissed"))
        assertEquals(ReportStatusEnum.REVIEWED, ReportStatusEnum.fromValue("REVIEWED"))
        assertEquals(ReportStatusEnum.PENDING, ReportStatusEnum.fromValue("unknown_value"))

        assertEquals(ModerationPostStatus.PUBLISHED, ModerationPostStatus.fromValue("PUBLISHED"))
        assertEquals(ModerationPostStatus.TEMPORARILY_HIDDEN, ModerationPostStatus.fromValue("TEMPORARILY_HIDDEN"))
        assertEquals(ModerationPostStatus.DELETED, ModerationPostStatus.fromValue("deleted"))
    }

    // ─────────────────────────────────────────
    // 2. Repository Contract & Moderation Tests
    // ─────────────────────────────────────────

    @Test
    fun testRepositoryGetAdminReports() = runBlocking {
        val fakeRepo = FakeCommunityRepository(
            reports = listOf(
                CommunityReport(
                    id = "r1",
                    postId = "p1",
                    commentId = null,
                    reporterId = "u1",
                    reporterUsername = "reporter1",
                    reason = "Misinformation",
                    status = ReportStatusEnum.PENDING,
                    targetContent = "Suspicious claim",
                    targetAuthorUsername = "author1",
                    createdAt = "2026-09-24T10:00:00Z",
                    updatedAt = null
                )
            ),
            actions = listOf(
                ModerationAction(
                    id = "a1",
                    action = "REMOVE_POST",
                    moderatorId = "m1",
                    moderatorUsername = "mod1",
                    postId = "p1",
                    commentId = null,
                    reportId = "r1",
                    reason = "Violation",
                    details = null,
                    createdAt = "2026-09-24T11:00:00Z"
                )
            )
        )

        val result = fakeRepo.getAdminReports(null, null, null, 50, 0)
        assertTrue(result.isSuccess)
        val list = result.getOrNull()
        assertNotNull(list)
        assertEquals(1, list!!.size)
        assertEquals("r1", list[0].id)
    }

    @Test
    fun testRepositoryForbidden403Handling() = runBlocking {
        val fakeRepo = FakeCommunityRepository(
            shouldFailWithForbidden = true
        )

        val result = fakeRepo.getAdminReports(null, null, null, 50, 0)
        assertTrue(result.isFailure)
        val ex = result.exceptionOrNull()
        assertTrue(ex is SecurityException)
        assertTrue(ex?.message?.contains("Access Denied", ignoreCase = true) == true)
    }

    @Test
    fun testRepositoryPostModerationOperations() = runBlocking {
        val fakeRepo = FakeCommunityRepository()

        val restoreRes = fakeRepo.restoreAdminPost("post_test")
        assertTrue(restoreRes.isSuccess)
        assertEquals("post_test", fakeRepo.lastRestoredPostId)

        val removeRes = fakeRepo.removeAdminPost("post_remove")
        assertTrue(removeRes.isSuccess)
        assertEquals("post_remove", fakeRepo.lastRemovedPostId)

        val deleteRes = fakeRepo.deleteAdminPost("post_delete")
        assertTrue(deleteRes.isSuccess)
        assertEquals("post_delete", fakeRepo.lastDeletedPostId)

        val deleteCommRes = fakeRepo.deleteAdminComment("comm_delete")
        assertTrue(deleteCommRes.isSuccess)
        assertEquals("comm_delete", fakeRepo.lastDeletedCommentId)

        val updateReportRes = fakeRepo.updateReportStatus("rep_test", "REVIEWED")
        assertTrue(updateReportRes.isSuccess)
        assertEquals("rep_test", fakeRepo.lastUpdatedReportId)
        assertEquals("REVIEWED", fakeRepo.lastUpdatedReportStatus)
    }

    // ─────────────────────────────────────────
    // Fake Repository for Testing
    // ─────────────────────────────────────────

    private class FakeCommunityRepository(
        private val reports: List<CommunityReport> = emptyList(),
        private val actions: List<ModerationAction> = emptyList(),
        private val shouldFailWithForbidden: Boolean = false
    ) : CommunityRepository {

        var lastRestoredPostId: String? = null
        var lastRemovedPostId: String? = null
        var lastDeletedPostId: String? = null
        var lastDeletedCommentId: String? = null
        var lastUpdatedReportId: String? = null
        var lastUpdatedReportStatus: String? = null

        override suspend fun getAdminReports(
            status: String?,
            postId: String?,
            commentId: String?,
            limit: Int,
            offset: Int
        ): Result<List<CommunityReport>> {
            if (shouldFailWithForbidden) {
                return Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
            }
            val filtered = if (status != null) {
                reports.filter { it.status.value.equals(status, ignoreCase = true) }
            } else {
                reports
            }
            return Result.success(filtered)
        }

        override suspend fun updateReportStatus(reportId: String, status: String): Result<Unit> {
            lastUpdatedReportId = reportId
            lastUpdatedReportStatus = status
            return Result.success(Unit)
        }

        override suspend fun getAdminPost(postId: String): Result<CommunityPost> {
            return Result.success(
                CommunityPost(
                    id = postId,
                    authorId = "author_1",
                    postType = "GENERAL",
                    stockSymbol = null,
                    content = "Test post content",
                    imageUrl = null,
                    likeCount = 5,
                    commentCount = 2,
                    reportCount = 1,
                    status = "PUBLISHED",
                    removedReason = null,
                    likedByMe = false,
                    createdAt = "2026-09-24T10:00:00Z",
                    updatedAt = "2026-09-24T10:00:00Z"
                )
            )
        }

        override suspend fun deleteAdminPost(postId: String): Result<Unit> {
            lastDeletedPostId = postId
            return Result.success(Unit)
        }

        override suspend fun restoreAdminPost(postId: String): Result<Unit> {
            lastRestoredPostId = postId
            return Result.success(Unit)
        }

        override suspend fun removeAdminPost(postId: String): Result<Unit> {
            lastRemovedPostId = postId
            return Result.success(Unit)
        }

        override suspend fun deleteAdminComment(commentId: String): Result<Unit> {
            lastDeletedCommentId = commentId
            return Result.success(Unit)
        }

        override suspend fun getModerationActions(
            postId: String?,
            commentId: String?,
            limit: Int
        ): Result<List<ModerationAction>> {
            if (shouldFailWithForbidden) {
                return Result.failure(SecurityException("Access Denied"))
            }
            return Result.success(actions)
        }

        // Stubbed normal methods
        override suspend fun getMyProfile(): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityProfile> = TODO()
        override suspend fun getUserProfile(userId: String): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityProfile> = TODO()
        override suspend fun getMyPosts(cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPostList> = TODO()
        override suspend fun getUserPosts(userId: String, cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPostList> = TODO()
        override suspend fun getFollowers(userId: String, cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList> = TODO()
        override suspend fun getFollowing(userId: String, cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList> = TODO()
        override suspend fun getCommunityNotifications(page: Int?, limit: Int?, unreadOnly: Boolean?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityNotificationList> = TODO()
        override suspend fun getUnreadNotificationCount(): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityUnreadCount> = TODO()
        override suspend fun markNotificationAsRead(notificationId: String): Result<Unit> = TODO()
        override suspend fun markAllNotificationsAsRead(): Result<Unit> = TODO()
        override suspend fun createPost(
            content: String,
            postType: String,
            stockSymbol: String?,
            imageBytes: ByteArray?,
            imageFileName: String?,
            imageMimeType: String?
        ): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPost> = TODO()
        override suspend fun getCommunityFeed(
            stockSymbol: String?,
            postType: String?,
            mine: Boolean?,
            following: Boolean?,
            cursor: String?,
            limit: Int?
        ): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPostList> = TODO()

        override suspend fun likePost(postId: String): Result<Unit> {
            TODO("Not yet implemented")
        }

        override suspend fun unlikePost(postId: String): Result<Unit> {
            TODO("Not yet implemented")
        }

        override suspend fun getComments(
            postId: String,
            cursor: String?,
            limit: Int?
        ): Result<CommunityCommentList> {
            TODO("Not yet implemented")
        }

        override suspend fun createComment(
            postId: String,
            content: String,
            parentCommentId: String?
        ): Result<CommunityComment> {
            TODO("Not yet implemented")
        }
    }
}
