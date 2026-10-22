package com.fyp.basarattradeinvest.feature.profile

import com.fyp.basarattradeinvest.domain.model.auth.UserProfile

sealed interface ProfileUiState {
    data object Loading : ProfileUiState
    data class Success(val profile: UserProfile) : ProfileUiState
    data class Error(val message: String) : ProfileUiState
}
