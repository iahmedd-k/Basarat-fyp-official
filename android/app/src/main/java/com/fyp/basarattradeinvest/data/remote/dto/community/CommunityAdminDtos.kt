package com.fyp.basarattradeinvest.data.remote.dto.community

import com.google.gson.annotations.SerializedName

/**
 * Community Admin and Moderation DTOs matching backend OpenAPI specification.
 * Source of truth: live OpenAPI at /api/v1/openapi.json
 */

/**
 * Single report DTO for GET /api/v1/admin/community/reports
 */
data class CommunityReportDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("post_id")
    val postId: String? = null,

    @SerializedName("comment_id")
    val commentId: String? = null,

    @SerializedName("reporter_id")
    val reporterId: String? = null,

    @SerializedName("user_id")
    val userId: String? = null,

    @SerializedName("reporter_username")
    val reporterUsername: String? = null,

    @SerializedName("reason")
    val reason: String,

    @SerializedName("status")
    val status: String, // PENDING, DISMISSED, REVIEWED

    @SerializedName("target_content")
    val targetContent: String? = null,

    @SerializedName("target_author_username")
    val targetAuthorUsername: String? = null,

    @SerializedName("created_at")
    val createdAt: String,

    @SerializedName("updated_at")
    val updatedAt: String? = null
)

/**
 * Wrapped response for reports list if returned as an object.
 */
data class CommunityReportListResponseDto(
    @SerializedName("reports")
    val reports: List<CommunityReportDto>? = null,

    @SerializedName("items")
    val items: List<CommunityReportDto>? = null,

    @SerializedName("total")
    val total: Int? = null,

    @SerializedName("limit")
    val limit: Int? = null,

    @SerializedName("offset")
    val offset: Int? = null
) {
    val reportList: List<CommunityReportDto>
        get() = reports ?: items ?: emptyList()
}

/**
 * Request body for PATCH /api/v1/admin/community/reports/{report_id}
 * Schema: CommunityReportStatusUpdate
 * Required: status (ReportStatus: "PENDING" | "DISMISSED" | "REVIEWED")
 */
data class CommunityReportStatusUpdateRequest(
    @SerializedName("status")
    val status: String
)

/**
 * Single moderation audit log entry DTO for GET /api/v1/admin/community/moderation-actions
 */
data class ModerationActionDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("action")
    val action: String? = null,

    @SerializedName("action_type")
    val actionType: String? = null,

    @SerializedName("moderator_id")
    val moderatorId: String? = null,

    @SerializedName("moderator_username")
    val moderatorUsername: String? = null,

    @SerializedName("post_id")
    val postId: String? = null,

    @SerializedName("comment_id")
    val commentId: String? = null,

    @SerializedName("report_id")
    val reportId: String? = null,

    @SerializedName("reason")
    val reason: String? = null,

    @SerializedName("details")
    val details: String? = null,

    @SerializedName("created_at")
    val createdAt: String? = null,

    @SerializedName("timestamp")
    val timestamp: String? = null
) {
    val effectiveAction: String
        get() = action ?: actionType ?: "MODERATION_ACTION"

    val effectiveTimestamp: String
        get() = createdAt ?: timestamp ?: ""
}

/**
 * Wrapped moderation actions list if returned as an object.
 */
data class ModerationActionsListResponseDto(
    @SerializedName("actions")
    val actions: List<ModerationActionDto>? = null,

    @SerializedName("items")
    val items: List<ModerationActionDto>? = null,

    @SerializedName("total")
    val total: Int? = null
) {
    val actionList: List<ModerationActionDto>
        get() = actions ?: items ?: emptyList()
}
