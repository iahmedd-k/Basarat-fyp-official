package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityFollowListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityNotificationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityNotificationsListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityPostResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityProfileResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityUnreadCountResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.community.CommunityUserSummaryDto
import com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotification
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotificationList
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityPostList
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.domain.model.community.CommunityUnreadCount
import com.fyp.basarattradeinvest.domain.model.community.CommunityUserSummary

/**
 * Mapper for converting Community DTOs to Domain Models.
 */
object CommunityDtoMapper {

    fun mapProfileDtoToDomain(dto: CommunityProfileResponseDto): CommunityProfile {
        return CommunityProfile(
            id = dto.id,
            username = dto.username,
            fullName = dto.fullName,
            avatarUrl = dto.avatarUrl,
            followersCount = dto.followersCount,
            followingCount = dto.followingCount,
            publishedPostCount = dto.publishedPostCount,
            isFollowing = dto.isFollowing,
            isOwnProfile = dto.isOwnProfile
        )
    }

    fun mapUserSummaryDtoToDomain(dto: CommunityUserSummaryDto): CommunityUserSummary {
        return CommunityUserSummary(
            id = dto.id,
            username = dto.username,
            fullName = dto.fullName,
            avatarUrl = dto.avatarUrl
        )
    }

    fun mapFollowListDtoToDomain(dto: CommunityFollowListResponseDto): CommunityFollowList {
        return CommunityFollowList(
            users = dto.users.map { mapUserSummaryDtoToDomain(it) },
            cursor = dto.cursor,
            hasMore = dto.hasMore
        )
    }

    fun mapPostDtoToDomain(dto: CommunityPostResponseDto): CommunityPost {
        return CommunityPost(
            id = dto.id,
            authorId = dto.authorId,
            postType = dto.postType,
            stockSymbol = dto.stockSymbol,
            content = dto.content,
            imageUrl = dto.imageUrl,
            likeCount = dto.likeCount,
            commentCount = dto.commentCount,
            reportCount = dto.reportCount,
            status = dto.status,
            removedReason = dto.removedReason,
            likedByMe = dto.likedByMe,
            createdAt = dto.createdAt,
            updatedAt = dto.updatedAt,
            authorUsername = dto.authorUsername,
            authorFullName = dto.authorFullName,
            authorAvatarUrl = dto.authorAvatarUrl,
            stockName = dto.stockName
        )
    }

    fun mapPostListDtoToDomain(dto: CommunityPostListResponseDto): CommunityPostList {
        val mappedPosts = dto.posts.map { mapPostDtoToDomain(it) }
            .distinctBy { it.id }
            .distinctBy { "${it.authorDisplayName}_${it.content.trim()}" }
        return CommunityPostList(
            posts = mappedPosts,
            cursor = dto.cursor,
            hasMore = dto.hasMore
        )
    }

    fun mapNotificationDtoToDomain(dto: CommunityNotificationResponseDto): CommunityNotification {
        return CommunityNotification(
            id = dto.id,
            recipientId = dto.recipientId,
            actorId = dto.actorId,
            actorUsername = dto.actorUsername,
            postId = dto.postId,
            commentId = dto.commentId,
            type = dto.type,
            title = dto.title,
            message = dto.message,
            isRead = dto.isRead,
            createdAt = dto.createdAt
        )
    }

    fun mapNotificationListDtoToDomain(dto: CommunityNotificationsListResponseDto): CommunityNotificationList {
        return CommunityNotificationList(
            notifications = dto.notifications.map { mapNotificationDtoToDomain(it) },
            total = dto.total,
            page = dto.page,
            limit = dto.limit,
            hasMore = dto.hasMore
        )
    }

    fun mapUnreadCountDtoToDomain(dto: CommunityUnreadCountResponseDto): CommunityUnreadCount {
        return CommunityUnreadCount(
            unreadCount = dto.totalUnread
        )
    }

    fun mapReportDtoToDomain(dto: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportDto): com.fyp.basarattradeinvest.domain.model.community.CommunityReport {
        return com.fyp.basarattradeinvest.domain.model.community.CommunityReport(
            id = dto.id,
            postId = dto.postId,
            commentId = dto.commentId,
            reporterId = dto.reporterId ?: dto.userId,
            reporterUsername = dto.reporterUsername,
            reason = dto.reason,
            status = com.fyp.basarattradeinvest.domain.model.community.ReportStatusEnum.fromValue(dto.status),
            targetContent = dto.targetContent,
            targetAuthorUsername = dto.targetAuthorUsername,
            createdAt = dto.createdAt,
            updatedAt = dto.updatedAt
        )
    }

    fun mapModerationActionDtoToDomain(dto: com.fyp.basarattradeinvest.data.remote.dto.community.ModerationActionDto): com.fyp.basarattradeinvest.domain.model.community.ModerationAction {
        return com.fyp.basarattradeinvest.domain.model.community.ModerationAction(
            id = dto.id,
            action = dto.effectiveAction,
            moderatorId = dto.moderatorId,
            moderatorUsername = dto.moderatorUsername,
            postId = dto.postId,
            commentId = dto.commentId,
            reportId = dto.reportId,
            reason = dto.reason,
            details = dto.details,
            createdAt = dto.effectiveTimestamp
        )
    }

    fun mapCommentDtoToDomain(dto: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentResponseDto): com.fyp.basarattradeinvest.domain.model.community.CommunityComment {
        return com.fyp.basarattradeinvest.domain.model.community.CommunityComment(
            id = dto.id,
            postId = dto.postId,
            authorId = dto.authorId,
            authorUsername = dto.authorUsername,
            authorFullName = dto.authorFullName,
            authorAvatarUrl = dto.authorAvatarUrl,
            parentCommentId = dto.parentCommentId,
            content = dto.content,
            status = dto.status ?: "PUBLISHED",
            replyCount = dto.replyCount,
            createdAt = dto.createdAt,
            updatedAt = dto.updatedAt
        )
    }

    fun mapCommentListDtoToDomain(dto: com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentListResponseDto): com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList {
        return com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList(
            comments = dto.comments.map { mapCommentDtoToDomain(it) },
            cursor = dto.cursor,
            hasMore = dto.hasMore
        )
    }
}

