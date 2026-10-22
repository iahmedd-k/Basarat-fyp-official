package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityFollowListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityNotificationsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityProfileResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityUnreadCountResponseDto
import okhttp3.MultipartBody
import okhttp3.RequestBody
import retrofit2.Response
import retrofit2.http.GET
import retrofit2.http.Multipart
import retrofit2.http.POST
import retrofit2.http.Part
import retrofit2.http.Path
import retrofit2.http.Query

/**
 * Retrofit service for Community endpoints.
 * Source of truth: live OpenAPI at /api/v1/openapi.json
 */
interface CommunityApiService {

    /**
     * Create a new community post (multipart form-data)
     */
    @Multipart
    @POST("api/v1/community/posts")
    suspend fun createPost(
        @Part("content") content: RequestBody,
        @Part("post_type") postType: RequestBody,
        @Part("stock_symbol") stockSymbol: RequestBody? = null,
        @Part image: MultipartBody.Part? = null
    ): Response<CommunityPostResponseDto>

    /**
     * Get community feed
     */
    @GET("api/v1/community/feed")
    suspend fun getCommunityFeed(
        @Query("stock_symbol") stockSymbol: String? = null,
        @Query("post_type") postType: String? = null,
        @Query("mine") mine: Boolean? = null,
        @Query("following") following: Boolean? = null,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 20
    ): Response<CommunityPostListResponseDto>

    /**
     * Like a post (204 No Content)
     */
    @POST("api/v1/community/posts/{post_id}/like")
    suspend fun likePost(
        @Path("post_id") postId: String
    ): Response<Unit>

    /**
     * Unlike a post (204 No Content)
     */
    @retrofit2.http.DELETE("api/v1/community/posts/{post_id}/like")
    suspend fun unlikePost(
        @Path("post_id") postId: String
    ): Response<Unit>

    /**
     * Get comments for a post
     */
    @GET("api/v1/community/posts/{post_id}/comments")
    suspend fun getComments(
        @Path("post_id") postId: String,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 50
    ): Response<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentListResponseDto>

    /**
     * Create a comment on a post
     */
    @POST("api/v1/community/posts/{post_id}/comments")
    suspend fun createComment(
        @Path("post_id") postId: String,
        @retrofit2.http.Body body: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentCreateDto
    ): Response<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentResponseDto>

    /**
     * Get user's followers
     */
    @GET("api/v1/community/users/{user_id}/followers")
    suspend fun getFollowers(
        @Path("user_id") userId: String,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 20
    ): Response<CommunityFollowListResponseDto>

    /**
     * Get users that user is following
     */
    @GET("api/v1/community/users/{user_id}/following")
    suspend fun getFollowing(
        @Path("user_id") userId: String,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 20
    ): Response<CommunityFollowListResponseDto>

    /**
     * Get current user's community profile
     */
    @GET("api/v1/community/me")
    suspend fun getMyCommunityProfile(): Response<CommunityProfileResponseDto>

    /**
     * Get current user's posts
     */
    @GET("api/v1/community/me/posts")
    suspend fun getMyPosts(
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 20
    ): Response<CommunityPostListResponseDto>

    /**
     * Get another user's public community profile
     */
    @GET("api/v1/community/users/{user_id}")
    suspend fun getUserProfile(
        @Path("user_id") userId: String
    ): Response<CommunityProfileResponseDto>

    /**
     * Get another user's public posts
     */
    @GET("api/v1/community/users/{user_id}/posts")
    suspend fun getUserPosts(
        @Path("user_id") userId: String,
        @Query("cursor") cursor: String? = null,
        @Query("limit") limit: Int? = 20
    ): Response<CommunityPostListResponseDto>

    /**
     * Get community notifications
     */
    @GET("api/v1/community/notifications")
    suspend fun getCommunityNotifications(
        @Query("page") page: Int? = 1,
        @Query("limit") limit: Int? = 20,
        @Query("unread_only") unreadOnly: Boolean? = false
    ): Response<CommunityNotificationsListResponseDto>

    /**
     * Get unread notification count
     */
    @GET("api/v1/community/notifications/unread-count")
    suspend fun getUnreadNotificationCount(): Response<CommunityUnreadCountResponseDto>

    /**
     * Mark notification as read
     */
    @POST("api/v1/community/notifications/{notification_id}/read")
    suspend fun markNotificationAsRead(
        @Path("notification_id") notificationId: String
    ): Response<Unit>

    /**
     * Mark all notifications as read
     */
    @POST("api/v1/community/notifications/read-all")
    suspend fun markAllNotificationsAsRead(): Response<Unit>

    // ==========================================
    // ADMIN COMMUNITY / MODERATION ENDPOINTS
    // ==========================================

    /**
     * GET /api/v1/admin/community/reports
     * Get reports for admin review.
     */
    @GET("api/v1/admin/community/reports")
    suspend fun getAdminReports(
        @Query("status") status: String? = null,
        @Query("post_id") postId: String? = null,
        @Query("comment_id") commentId: String? = null,
        @Query("limit") limit: Int? = 50,
        @Query("offset") offset: Int? = 0
    ): Response<com.google.gson.JsonElement>

    /**
     * PATCH /api/v1/admin/community/reports/{report_id}
     * Update report status (PENDING, DISMISSED, REVIEWED)
     */
    @retrofit2.http.PATCH("api/v1/admin/community/reports/{report_id}")
    suspend fun updateReportStatus(
        @Path("report_id") reportId: String,
        @retrofit2.http.Body body: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportStatusUpdateRequest
    ): Response<com.google.gson.JsonElement>

    /**
     * GET /api/v1/admin/community/posts/{post_id}
     * Get post for admin review
     */
    @GET("api/v1/admin/community/posts/{post_id}")
    suspend fun getAdminPost(
        @Path("post_id") postId: String
    ): Response<CommunityPostResponseDto>

    /**
     * DELETE /api/v1/admin/community/posts/{post_id}
     * Delete a post (admin) - 204 No Content
     */
    @retrofit2.http.DELETE("api/v1/admin/community/posts/{post_id}")
    suspend fun deleteAdminPost(
        @Path("post_id") postId: String
    ): Response<Unit>

    /**
     * POST /api/v1/admin/community/posts/{post_id}/restore
     * Restore a temporarily hidden post - 204 No Content
     */
    @POST("api/v1/admin/community/posts/{post_id}/restore")
    suspend fun restoreAdminPost(
        @Path("post_id") postId: String
    ): Response<Unit>

    /**
     * POST /api/v1/admin/community/posts/{post_id}/remove
     * Directly remove a post (admin) - 204 No Content
     */
    @POST("api/v1/admin/community/posts/{post_id}/remove")
    suspend fun removeAdminPost(
        @Path("post_id") postId: String
    ): Response<Unit>

    /**
     * DELETE /api/v1/admin/community/comments/{comment_id}
     * Delete a comment (admin) - 204 No Content
     */
    @retrofit2.http.DELETE("api/v1/admin/community/comments/{comment_id}")
    suspend fun deleteAdminComment(
        @Path("comment_id") commentId: String
    ): Response<Unit>

    /**
     * GET /api/v1/admin/community/moderation-actions
     * Get moderation audit log
     */
    @GET("api/v1/admin/community/moderation-actions")
    suspend fun getModerationActions(
        @Query("post_id") postId: String? = null,
        @Query("comment_id") commentId: String? = null,
        @Query("limit") limit: Int? = 50
    ): Response<com.google.gson.JsonElement>
}

