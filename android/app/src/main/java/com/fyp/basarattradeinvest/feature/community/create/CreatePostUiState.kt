package com.fyp.basarattradeinvest.feature.community.create

import com.fyp.basarattradeinvest.domain.model.community.CommunityPost

sealed interface CreatePostUiState {
    data object Idle : CreatePostUiState
    data object Submitting : CreatePostUiState
    data class Success(val post: CommunityPost) : CreatePostUiState
    data class Error(val message: String) : CreatePostUiState
}
