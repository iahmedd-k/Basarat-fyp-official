package com.fyp.basarattradeinvest.data.remote.dto.community

import com.google.gson.annotations.SerializedName

/**
 * Community DTOs matching backend OpenAPI specification.
 * Source of truth: live OpenAPI at /api/v1/openapi.json
 */

/**
 * Community Profile response for both /community/me and /community/users/{user_id}
 */
data class CommunityProfileResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("username")
    val username: String,

    @SerializedName("full_name")
    val fullName: String? = null,

    @SerializedName("avatar_url")
    val avatarUrl: String? = null,

    @SerializedName("followers_count")
    val followersCount: Int,

    @SerializedName("following_count")
    val followingCount: Int,

    @SerializedName("published_post_count")
    val publishedPostCount: Int,

    @SerializedName("is_following")
    val isFollowing: Boolean = false,

    @SerializedName("is_own_profile")
    val isOwnProfile: Boolean = false
)

/**
 * User summary in followers/following list
 */
data class CommunityUserSummaryDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("username")
    val username: String,

    @SerializedName("full_name")
    val fullName: String? = null,

    @SerializedName("avatar_url")
    val avatarUrl: String? = null
)

/**
 * Followers and Following paginated list response
 */
data class CommunityFollowListResponseDto(
    @SerializedName("users")
    val users: List<CommunityUserSummaryDto>,

    @SerializedName("cursor")
    val cursor: String? = null,

    @SerializedName("has_more")
    val hasMore: Boolean
)

/**
 * Community Post response
 */
data class CommunityPostResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("author_id")
    val authorId: String,

    @SerializedName("author_username")
    val authorUsername: String? = null,

    @SerializedName("author_full_name")
    val authorFullName: String? = null,

    @SerializedName("author_avatar_url")
    val authorAvatarUrl: String? = null,

    @SerializedName("post_type")
    val postType: String,

    @SerializedName("stock_symbol")
    val stockSymbol: String? = null,

    @SerializedName("stock_name")
    val stockName: String? = null,

    @SerializedName("content")
    val content: String,

    @SerializedName("image_url")
    val imageUrl: String? = null,

    @SerializedName("like_count")
    val likeCount: Int,

    @SerializedName("comment_count")
    val commentCount: Int,

    @SerializedName("report_count")
    val reportCount: Int = 0,

    @SerializedName("status")
    val status: String,

    @SerializedName("removed_reason")
    val removedReason: String? = null,

    @SerializedName("liked_by_me")
    val likedByMe: Boolean = false,

    @SerializedName("created_at")
    val createdAt: String,

    @SerializedName("updated_at")
    val updatedAt: String
)

/**
 * Community Posts paginated list response
 */
data class CommunityPostListResponseDto(
    @SerializedName("posts")
    val posts: List<CommunityPostResponseDto>,

    @SerializedName("cursor")
    val cursor: String? = null,

    @SerializedName("has_more")
    val hasMore: Boolean
)

/**
 * Community Notification response
 */
data class CommunityNotificationResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("recipient_id")
    val recipientId: String,

    @SerializedName("actor_id")
    val actorId: String? = null,

    @SerializedName("actor_username")
    val actorUsername: String? = null,

    @SerializedName("post_id")
    val postId: String? = null,

    @SerializedName("comment_id")
    val commentId: String? = null,

    @SerializedName("type")
    val type: String,

    @SerializedName("title")
    val title: String,

    @SerializedName("message")
    val message: String,

    @SerializedName("is_read")
    val isRead: Boolean,

    @SerializedName("created_at")
    val createdAt: String
)

/**
 * Community Notifications paginated list response
 */
data class CommunityNotificationsListResponseDto(
    @SerializedName("notifications")
    val notifications: List<CommunityNotificationResponseDto>,

    @SerializedName("total")
    val total: Int,

    @SerializedName("page")
    val page: Int,

    @SerializedName("limit")
    val limit: Int,

    @SerializedName("has_more")
    val hasMore: Boolean
)

/**
 * Community unread notification count response
 */
data class CommunityUnreadCountResponseDto(
    @SerializedName("count")
    val count: Int? = null,

    @SerializedName("unread_count")
    val unreadCount: Int? = null
) {
    val totalUnread: Int
        get() = count ?: unreadCount ?: 0
}

/**
 * Request body for creating a comment on a post
 */
data class CommunityCommentCreateDto(
    @SerializedName("content")
    val content: String,

    @SerializedName("parent_comment_id")
    val parentCommentId: String? = null
)

/**
 * Single comment response matching backend OpenAPI schema
 */
data class CommunityCommentResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("post_id")
    val postId: String,

    @SerializedName("author_id")
    val authorId: String,

    @SerializedName("author_username")
    val authorUsername: String? = null,

    @SerializedName("author_full_name")
    val authorFullName: String? = null,

    @SerializedName("author_avatar_url")
    val authorAvatarUrl: String? = null,

    @SerializedName("parent_comment_id")
    val parentCommentId: String? = null,

    @SerializedName("content")
    val content: String,

    @SerializedName("status")
    val status: String? = "PUBLISHED",

    @SerializedName("reply_count")
    val replyCount: Int = 0,

    @SerializedName("created_at")
    val createdAt: String,

    @SerializedName("updated_at")
    val updatedAt: String? = null
)

/**
 * Paginated comment list response
 */
data class CommunityCommentListResponseDto(
    @SerializedName("comments")
    val comments: List<CommunityCommentResponseDto> = emptyList(),

    @SerializedName("cursor")
    val cursor: String? = null,

    @SerializedName("has_more")
    val hasMore: Boolean = false
)
