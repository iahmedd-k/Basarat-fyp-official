package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.core.network.NetworkErrorParser
import com.fyp.basarattradeinvest.data.mapper.CommunityDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.CommunityApiService
import com.fyp.basarattradeinvest.domain.model.community.CommunityFollowList
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotification
import com.fyp.basarattradeinvest.domain.model.community.CommunityNotificationList
import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityPostList
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile
import com.fyp.basarattradeinvest.domain.model.community.CommunityUnreadCount
import com.fyp.basarattradeinvest.domain.model.community.CommunityUserSummary
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import kotlinx.coroutines.CancellationException
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.MultipartBody
import okhttp3.RequestBody.Companion.toRequestBody

/**
 * Implementation of CommunityRepository consuming live backend Community endpoints.
 */
class CommunityRepositoryImpl(
    private val apiService: CommunityApiService = NetworkClient.communityApiService
) : CommunityRepository {

    override suspend fun createPost(
        content: String,
        postType: String,
        stockSymbol: String?,
        imageBytes: ByteArray?,
        imageFileName: String?,
        imageMimeType: String?
    ): Result<CommunityPost> {
        return try {
            val contentBody = content.toRequestBody("text/plain".toMediaTypeOrNull())
            val postTypeBody = postType.toRequestBody("text/plain".toMediaTypeOrNull())
            val stockSymbolBody = if (!stockSymbol.isNullOrBlank() && postType.equals("STOCK", ignoreCase = true)) {
                stockSymbol.trim().uppercase().toRequestBody("text/plain".toMediaTypeOrNull())
            } else null

            val imagePart = if (imageBytes != null && !imageFileName.isNullOrBlank()) {
                val mediaType = (imageMimeType ?: "image/jpeg").toMediaTypeOrNull()
                val requestFile = imageBytes.toRequestBody(mediaType)
                MultipartBody.Part.createFormData("image", imageFileName, requestFile)
            } else null

            val response = apiService.createPost(
                content = contentBody,
                postType = postTypeBody,
                stockSymbol = stockSymbolBody,
                image = imagePart
            )

            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapPostDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getCommunityFeed(
        stockSymbol: String?,
        postType: String?,
        mine: Boolean?,
        following: Boolean?,
        cursor: String?,
        limit: Int?
    ): Result<CommunityPostList> {
        return try {
            val response = apiService.getCommunityFeed(
                stockSymbol = stockSymbol,
                postType = postType,
                mine = mine,
                following = following,
                cursor = cursor,
                limit = limit
            )
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapPostListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun likePost(postId: String): Result<Unit> {
        return try {
            val response = apiService.likePost(postId)
            if (response.isSuccessful || response.code() == 204) {
                Result.success(Unit)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun unlikePost(postId: String): Result<Unit> {
        return try {
            val response = apiService.unlikePost(postId)
            if (response.isSuccessful || response.code() == 204) {
                Result.success(Unit)
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getComments(postId: String, cursor: String?, limit: Int?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityCommentList> {
        return try {
            val response = apiService.getComments(postId, cursor, limit)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapCommentListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun createComment(postId: String, content: String, parentCommentId: String?): Result<com.fyp.basarattradeinvest.domain.model.community.CommunityComment> {
        return try {
            val body = com.fyp.basarattradeinvest.data.remote.dto.community.CommunityCommentCreateDto(
                content = content,
                parentCommentId = parentCommentId
            )
            val response = apiService.createComment(postId, body)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapCommentDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getMyProfile(): Result<CommunityProfile> {
        return try {
            val response = apiService.getMyCommunityProfile()
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapProfileDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getUserProfile(userId: String): Result<CommunityProfile> {
        return try {
            val response = apiService.getUserProfile(userId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapProfileDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getMyPosts(cursor: String?, limit: Int?): Result<CommunityPostList> {
        return try {
            val response = apiService.getMyPosts(cursor, limit)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapPostListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getUserPosts(userId: String, cursor: String?, limit: Int?): Result<CommunityPostList> {
        return try {
            val response = apiService.getUserPosts(userId, cursor, limit)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapPostListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getFollowers(userId: String, cursor: String?, limit: Int?): Result<CommunityFollowList> {
        return try {
            val response = apiService.getFollowers(userId, cursor, limit)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapFollowListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getFollowing(userId: String, cursor: String?, limit: Int?): Result<CommunityFollowList> {
        return try {
            val response = apiService.getFollowing(userId, cursor, limit)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapFollowListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getCommunityNotifications(
        page: Int?,
        limit: Int?,
        unreadOnly: Boolean?
    ): Result<CommunityNotificationList> {
        return try {
            val response = apiService.getCommunityNotifications(page, limit, unreadOnly)
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapNotificationListDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getUnreadNotificationCount(): Result<CommunityUnreadCount> {
        return try {
            val response = apiService.getUnreadNotificationCount()
            if (response.isSuccessful && response.body() != null) {
                Result.success(CommunityDtoMapper.mapUnreadCountDtoToDomain(response.body()!!))
            } else {
                val errorMsg = NetworkErrorParser.parseError(response)
                Result.failure(Exception(errorMsg))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun markNotificationAsRead(notificationId: String): Result<Unit> {
        return try {
            val response = apiService.markNotificationAsRead(notificationId)
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to mark notification as read: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun markAllNotificationsAsRead(): Result<Unit> {
        return try {
            val response = apiService.markAllNotificationsAsRead()
            if (response.isSuccessful) {
                Result.success(Unit)
            } else {
                Result.failure(Exception("Failed to mark all notifications as read: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    // ───────────────────────────────
    // Admin / Moderation operations
    // ───────────────────────────────

    override suspend fun getAdminReports(
        status: String?,
        postId: String?,
        commentId: String?,
        limit: Int,
        offset: Int
    ): Result<List<com.fyp.basarattradeinvest.domain.model.community.CommunityReport>> {
        return try {
            val response = apiService.getAdminReports(status, postId, commentId, limit, offset)
            when (response.code()) {
                200 -> {
                    val element = response.body()
                    val dtoList = parseReportsJson(element)
                    val domainReports = dtoList.map { CommunityDtoMapper.mapReportDtoToDomain(it) }
                    Result.success(domainReports)
                }
                401 -> Result.failure(IllegalStateException("Unauthorized. Please log in again."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Reports endpoint not found."))
                else -> Result.failure(Exception("Failed to fetch admin reports: ${response.code()} ${response.message()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun updateReportStatus(reportId: String, status: String): Result<Unit> {
        return try {
            val body = com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportStatusUpdateRequest(status = status)
            val response = apiService.updateReportStatus(reportId, body)
            when (response.code()) {
                200, 204 -> Result.success(Unit)
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Report with ID $reportId not found."))
                422 -> Result.failure(IllegalArgumentException("Validation error: Invalid report status $status"))
                else -> Result.failure(Exception("Failed to update report status: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getAdminPost(postId: String): Result<CommunityPost> {
        return try {
            val response = apiService.getAdminPost(postId)
            when (response.code()) {
                200 -> {
                    val body = response.body() ?: return Result.failure(NoSuchElementException("Post not found."))
                    Result.success(CommunityDtoMapper.mapPostDtoToDomain(body))
                }
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Post with ID $postId not found."))
                else -> Result.failure(Exception("Failed to fetch post for admin review: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun deleteAdminPost(postId: String): Result<Unit> {
        return try {
            val response = apiService.deleteAdminPost(postId)
            when (response.code()) {
                200, 204 -> Result.success(Unit)
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Post with ID $postId not found."))
                else -> Result.failure(Exception("Failed to delete post: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun restoreAdminPost(postId: String): Result<Unit> {
        return try {
            val response = apiService.restoreAdminPost(postId)
            when (response.code()) {
                200, 204 -> Result.success(Unit)
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Post with ID $postId not found."))
                else -> Result.failure(Exception("Failed to restore post: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun removeAdminPost(postId: String): Result<Unit> {
        return try {
            val response = apiService.removeAdminPost(postId)
            when (response.code()) {
                200, 204 -> Result.success(Unit)
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Post with ID $postId not found."))
                else -> Result.failure(Exception("Failed to remove post: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun deleteAdminComment(commentId: String): Result<Unit> {
        return try {
            val response = apiService.deleteAdminComment(commentId)
            when (response.code()) {
                200, 204 -> Result.success(Unit)
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                404 -> Result.failure(NoSuchElementException("Comment with ID $commentId not found."))
                else -> Result.failure(Exception("Failed to delete comment: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    override suspend fun getModerationActions(
        postId: String?,
        commentId: String?,
        limit: Int
    ): Result<List<com.fyp.basarattradeinvest.domain.model.community.ModerationAction>> {
        return try {
            val response = apiService.getModerationActions(postId, commentId, limit)
            when (response.code()) {
                200 -> {
                    val element = response.body()
                    val dtoList = parseActionsJson(element)
                    val domainActions = dtoList.map { CommunityDtoMapper.mapModerationActionDtoToDomain(it) }
                    Result.success(domainActions)
                }
                401 -> Result.failure(IllegalStateException("Unauthorized."))
                403 -> Result.failure(SecurityException("Access Denied: Administrator or Moderator privileges are required."))
                else -> Result.failure(Exception("Failed to fetch moderation actions: ${response.code()}"))
            }
        } catch (e: Exception) {
            Result.failure(e)
        }
    }

    private fun parseReportsJson(element: com.google.gson.JsonElement?): List<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportDto> {
        if (element == null || element.isJsonNull) return emptyList()
        val gson = com.google.gson.Gson()
        return try {
            if (element.isJsonArray) {
                gson.fromJson(element, Array<com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportDto>::class.java).toList()
            } else if (element.isJsonObject) {
                gson.fromJson(element, com.fyp.basarattradeinvest.data.remote.dto.community.CommunityReportListResponseDto::class.java).reportList
            } else {
                emptyList()
            }
        } catch (_: Exception) {
            emptyList()
        }
    }

    private fun parseActionsJson(element: com.google.gson.JsonElement?): List<com.fyp.basarattradeinvest.data.remote.dto.community.ModerationActionDto> {
        if (element == null || element.isJsonNull) return emptyList()
        val gson = com.google.gson.Gson()
        return try {
            if (element.isJsonArray) {
                gson.fromJson(element, Array<com.fyp.basarattradeinvest.data.remote.dto.community.ModerationActionDto>::class.java).toList()
            } else if (element.isJsonObject) {
                gson.fromJson(element, com.fyp.basarattradeinvest.data.remote.dto.community.ModerationActionsListResponseDto::class.java).actionList
            } else {
                emptyList()
            }
        } catch (_: Exception) {
            emptyList()
        }
    }
}
