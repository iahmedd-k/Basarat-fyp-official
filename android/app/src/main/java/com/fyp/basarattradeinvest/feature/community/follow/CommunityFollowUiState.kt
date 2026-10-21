package com.fyp.basarattradeinvest.feature.community.follow

import com.fyp.basarattradeinvest.domain.model.community.CommunityUserSummary

sealed interface CommunityFollowUiState {
    data object Loading : CommunityFollowUiState

    data class Success(
        val users: List<CommunityUserSummary>,
        val hasMore: Boolean,
        val isFollowingMode: Boolean,
        val isRefreshing: Boolean = false
    ) : CommunityFollowUiState

    data object Empty : CommunityFollowUiState

    data class Error(
        val message: String
    ) : CommunityFollowUiState
}
