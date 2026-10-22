package com.fyp.basarattradeinvest.domain.model.community

/**
 * Domain representation of a Community User Profile.
 */
data class CommunityProfile(
    val id: String,
    val username: String,
    val fullName: String?,
    val avatarUrl: String?,
    val followersCount: Int,
    val followingCount: Int,
    val publishedPostCount: Int,
    val isFollowing: Boolean,
    val isOwnProfile: Boolean
) {
    val displayName: String
        get() = if (!fullName.isNullOrBlank()) fullName else "@$username"
}

/**
 * Domain representation of a Community User in a list.
 */
data class CommunityUserSummary(
    val id: String,
    val username: String,
    val fullName: String?,
    val avatarUrl: String?
) {
    val displayName: String
        get() = if (!fullName.isNullOrBlank()) fullName else "@$username"
}

/**
 * Paginated follow list domain model.
 */
data class CommunityFollowList(
    val users: List<CommunityUserSummary>,
    val cursor: String?,
    val hasMore: Boolean
)

/**
 * Domain representation of a Community Post.
 */
data class CommunityPost(
    val id: String,
    val authorId: String,
    val postType: String,
    val stockSymbol: String?,
    val content: String,
    val imageUrl: String?,
    val likeCount: Int,
    val commentCount: Int,
    val reportCount: Int,
    val status: String,
    val removedReason: String?,
    val likedByMe: Boolean,
    val createdAt: String,
    val updatedAt: String,
    val authorUsername: String? = null,
    val authorFullName: String? = null,
    val authorAvatarUrl: String? = null,
    val stockName: String? = null
) {
    val isStockPost: Boolean
        get() = !stockSymbol.isNullOrBlank() || postType.equals("STOCK", ignoreCase = true)

    val authorDisplayName: String
        get() = if (!authorFullName.isNullOrBlank()) authorFullName else if (!authorUsername.isNullOrBlank()) "@$authorUsername" else "Trader #${authorId.take(8)}"
}

/**
 * Paginated post list domain model.
 */
data class CommunityPostList(
    val posts: List<CommunityPost>,
    val cursor: String?,
    val hasMore: Boolean
)

/**
 * Domain representation of a Community Notification.
 */
data class CommunityNotification(
    val id: String,
    val recipientId: String,
    val actorId: String?,
    val actorUsername: String?,
    val postId: String?,
    val commentId: String?,
    val type: String,
    val title: String,
    val message: String,
    val isRead: Boolean,
    val createdAt: String
)

/**
 * Paginated notification list domain model.
 */
data class CommunityNotificationList(
    val notifications: List<CommunityNotification>,
    val total: Int,
    val page: Int,
    val limit: Int,
    val hasMore: Boolean
)

/**
 * Unread count domain model.
 */
data class CommunityUnreadCount(
    val unreadCount: Int
)

/**
 * Report Status enum matching OpenAPI ReportStatus
 */
enum class ReportStatusEnum(val value: String) {
    PENDING("PENDING"),
    DISMISSED("DISMISSED"),
    REVIEWED("REVIEWED");

    companion object {
        fun fromValue(value: String?): ReportStatusEnum {
            return entries.firstOrNull { it.value.equals(value, ignoreCase = true) } ?: PENDING
        }
    }
}

/**
 * Post Status enum matching OpenAPI PostStatus
 */
enum class ModerationPostStatus(val value: String) {
    PUBLISHED("PUBLISHED"),
    TEMPORARILY_HIDDEN("TEMPORARILY_HIDDEN"),
    DELETED("DELETED");

    companion object {
        fun fromValue(value: String?): ModerationPostStatus {
            return entries.firstOrNull { it.value.equals(value, ignoreCase = true) } ?: PUBLISHED
        }
    }
}

/**
 * Admin Community Report domain model
 */
data class CommunityReport(
    val id: String,
    val postId: String?,
    val commentId: String?,
    val reporterId: String?,
    val reporterUsername: String?,
    val reason: String,
    val status: ReportStatusEnum,
    val targetContent: String?,
    val targetAuthorUsername: String?,
    val createdAt: String,
    val updatedAt: String?
) {
    val isPostReport: Boolean
        get() = !postId.isNullOrBlank()

    val isCommentReport: Boolean
        get() = !commentId.isNullOrBlank()

    val targetTypeLabel: String
        get() = if (isPostReport) "Post" else if (isCommentReport) "Comment" else "Content"
}

/**
 * Moderation Action audit log domain model
 */
data class ModerationAction(
    val id: String,
    val action: String,
    val moderatorId: String?,
    val moderatorUsername: String?,
    val postId: String?,
    val commentId: String?,
    val reportId: String?,
    val reason: String?,
    val details: String?,
    val createdAt: String
)

/**
 * Domain representation of a Community Comment.
 */
data class CommunityComment(
    val id: String,
    val postId: String,
    val authorId: String,
    val authorUsername: String?,
    val authorFullName: String?,
    val authorAvatarUrl: String?,
    val parentCommentId: String?,
    val content: String,
    val status: String,
    val replyCount: Int,
    val createdAt: String,
    val updatedAt: String?
) {
    val authorDisplayName: String
        get() = if (!authorFullName.isNullOrBlank()) authorFullName else if (!authorUsername.isNullOrBlank()) "@$authorUsername" else "Trader #${authorId.take(8)}"
}

/**
 * Paginated comment list domain model.
 */
data class CommunityCommentList(
    val comments: List<CommunityComment>,
    val cursor: String?,
    val hasMore: Boolean
)

