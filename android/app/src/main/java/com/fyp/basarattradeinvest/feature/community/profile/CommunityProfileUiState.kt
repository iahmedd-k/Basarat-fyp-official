package com.fyp.basarattradeinvest.feature.community.profile

import com.fyp.basarattradeinvest.domain.model.community.CommunityPost
import com.fyp.basarattradeinvest.domain.model.community.CommunityProfile

enum class CommunityFeedMode {
    COMMUNITY_FEED,
    MY_POSTS
}

sealed interface CommunityProfileUiState {
    data object Loading : CommunityProfileUiState

    data class Success(
        val profile: CommunityProfile,
        val posts: List<CommunityPost>,
        val hasMorePosts: Boolean,
        val isRefreshing: Boolean = false,
        val feedMode: CommunityFeedMode = CommunityFeedMode.COMMUNITY_FEED,
        val isPostsLoading: Boolean = false
    ) : CommunityProfileUiState

    data class Error(
        val message: String
    ) : CommunityProfileUiState
}
