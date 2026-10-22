package com.fyp.basarattradeinvest.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.data.repository.UsersRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.domain.usecase.user.GetCurrentUserProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.UpdateUserProfileUseCase
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class EditProfileViewModel(
    private val getCurrentUserProfileUseCase: GetCurrentUserProfileUseCase = GetCurrentUserProfileUseCase(UsersRepositoryImpl()),
    private val updateUserProfileUseCase: UpdateUserProfileUseCase = UpdateUserProfileUseCase(UsersRepositoryImpl())
) : ViewModel() {

    private val _currentProfile = MutableStateFlow<UserProfile?>(null)
    val currentProfile: StateFlow<UserProfile?> = _currentProfile.asStateFlow()

    private val _uiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val uiState: StateFlow<AuthUiState> = _uiState.asStateFlow()

    init {
        loadProfile()
    }

    fun loadProfile() {
        viewModelScope.launch {
            val result = getCurrentUserProfileUseCase()
            result.onSuccess { profile ->
                _currentProfile.value = profile
            }
        }
    }

    fun saveProfile(fullName: String, avatarUrl: String?) {
        val trimmedName = fullName.trim()
        if (trimmedName.isBlank()) {
            _uiState.value = AuthUiState.Error("Full Name cannot be empty")
            return
        }

        viewModelScope.launch {
            _uiState.value = AuthUiState.Loading
            val request = UpdateProfileRequestDto(
                fullName = trimmedName,
                avatarUrl = avatarUrl?.trim()?.takeIf { it.isNotBlank() }
            )
            val result = updateUserProfileUseCase(request)
            result.fold(
                onSuccess = { updated ->
                    _currentProfile.value = updated
                    _uiState.value = AuthUiState.Success(message = "Profile updated successfully!")
                },
                onFailure = { error ->
                    _uiState.value = AuthUiState.Error(
                        error.message ?: "Failed to update profile. Please try again."
                    )
                }
            )
        }
    }

    fun resetState() {
        _uiState.value = AuthUiState.Idle
    }
}
