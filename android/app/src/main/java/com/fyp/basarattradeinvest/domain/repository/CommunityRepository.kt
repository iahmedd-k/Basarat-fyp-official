package com.fyp.basarattradeinvest.domain.repository

import com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotificationList
import com.fyp.basarattradeinvest.domain.model.community.CommunityPostList
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.domain.model.community.CommunityUnreadCount

/**
 * Repository interface for Community operations.
 */
interface CommunityRepository {

    suspend fun createPost(
        content: String,
        postType: String,
        stockSymbol: String? = null,
        imageBytes: ByteArray? = null,
        imageFileName: String? = null,
        imageMimeType: String? = null
    ): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPost>

    suspend fun getCommunityFeed(
        stockSymbol: String? = null,
        postType: String? = null,
        mine: Boolean? = null,
        following: Boolean? = null,
        cursor: String? = null,
        limit: Int? = 20
    ): Result<CommunityPostList>

    suspend fun likePost(postId: String): Result<Unit>

    suspend fun unlikePost(postId: String): Result<Unit>

    suspend fun getComments(postId: String, cursor: String? = null, limit: Int? = 50): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList>

    suspend fun createComment(postId: String, content: String, parentCommentId: String? = null): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityComment>

    suspend fun getMyProfile(): Result<CommunityProfile>

    suspend fun getUserProfile(userId: String): Result<CommunityProfile>

    suspend fun getMyPosts(cursor: String? = null, limit: Int? = 20): Result<CommunityPostList>

    suspend fun getUserPosts(userId: String, cursor: String? = null, limit: Int? = 20): Result<CommunityPostList>

    suspend fun getFollowers(userId: String, cursor: String? = null, limit: Int? = 20): Result<CommunityFollowList>

    suspend fun getFollowing(userId: String, cursor: String? = null, limit: Int? = 20): Result<CommunityFollowList>

    suspend fun getCommunityNotifications(
        page: Int? = 1,
        limit: Int? = 20,
        unreadOnly: Boolean? = false
    ): Result<CommunityNotificationList>

    suspend fun getUnreadNotificationCount(): Result<CommunityUnreadCount>

    suspend fun markNotificationAsRead(notificationId: String): Result<Unit>

    suspend fun markAllNotificationsAsRead(): Result<Unit>

    // Admin / Moderation operations
    suspend fun getAdminReports(
        status: String? = null,
        postId: String? = null,
        commentId: String? = null,
        limit: Int = 50,
        offset: Int = 0
    ): Result<List<com.fyp.basarattradeinvest.domain.model.community.CommunityReport>>

    suspend fun updateReportStatus(reportId: String, status: String): Result<Unit>

    suspend fun getAdminPost(postId: String): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityPost>

    suspend fun deleteAdminPost(postId: String): Result<Unit>

    suspend fun restoreAdminPost(postId: String): Result<Unit>

    suspend fun removeAdminPost(postId: String): Result<Unit>

    suspend fun deleteAdminComment(commentId: String): Result<Unit>

    suspend fun getModerationActions(
        postId: String? = null,
        commentId: String? = null,
        limit: Int = 50
    ): Result<List<com.fyp.basarattradeinvest.domain.model.community.ModerationAction>>
}

