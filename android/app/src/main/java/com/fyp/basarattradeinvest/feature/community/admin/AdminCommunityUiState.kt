package com.fyp.basarattradeinvest.feature.community.admin

import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityReport
import com.fyp.basarattradeinvest.domain.model.community.ModerationAction

/**
 * UI State for Admin Reports List
 */
sealed interface AdminReportsUiState {
    data object Loading : AdminReportsUiState

    data class Success(
        val reports: List<CommunityReport>,
        val activeFilter: ReportStatusFilter
    ) : AdminReportsUiState

    data object Empty : AdminReportsUiState

    data class Error(
        val message: String,
        val isForbidden: Boolean = false
    ) : AdminReportsUiState
}

/**
 * UI State for Moderation Actions Audit Log
 */
sealed interface ModerationActionsUiState {
    data object Loading : ModerationActionsUiState

    data class Success(
        val actions: List<ModerationAction>
    ) : ModerationActionsUiState

    data object Empty : ModerationActionsUiState

    data class Error(
        val message: String,
        val isForbidden: Boolean = false
    ) : ModerationActionsUiState
}

/**
 * UI State for Admin Post Review
 */
sealed interface AdminPostReviewUiState {
    data object Idle : AdminPostReviewUiState
    data object Loading : AdminPostReviewUiState
    data class Success(val post: CommunityPost) : AdminPostReviewUiState
    data class Error(val message: String) : AdminPostReviewUiState
}

/**
 * Supported report status filters based on verified backend enums.
 */
enum class ReportStatusFilter(val label: String, val apiValue: String?) {
    ALL("All", null),
    PENDING("Pending", "PENDING"),
    REVIEWED("Reviewed", "REVIEWED"),
    DISMISSED("Dismissed", "DISMISSED")
}
