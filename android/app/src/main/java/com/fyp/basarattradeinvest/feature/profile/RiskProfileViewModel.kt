package com.fyp.basarattradeinvest.feature.profile

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.remote.dto.user.UpdateProfileRequestDto
import com.fyp.basarattradeinvest.data.repository.UsersRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.auth.InvestmentProfileOptions
import com.fyp.basarattradeinvest.domain.model.auth.UserProfile
import com.fyp.basarattradeinvest.domain.usecase.user.GetCurrentUserProfileUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.GetInvestmentProfileOptionsUseCase
import com.fyp.basarattradeinvest.domain.usecase.user.UpdateUserProfileUseCase
import com.fyp.basarattradeinvest.feature.auth.AuthUiState
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RiskProfileViewModel(
    private val getInvestmentProfileOptionsUseCase: GetInvestmentProfileOptionsUseCase = GetInvestmentProfileOptionsUseCase(UsersRepositoryImpl()),
    private val getCurrentUserProfileUseCase: GetCurrentUserProfileUseCase = GetCurrentUserProfileUseCase(UsersRepositoryImpl()),
    private val updateUserProfileUseCase: UpdateUserProfileUseCase = UpdateUserProfileUseCase(UsersRepositoryImpl())
) : ViewModel() {

    private val _uiState = MutableStateFlow<RiskProfileUiState>(RiskProfileUiState.Loading)
    val uiState: StateFlow<RiskProfileUiState> = _uiState.asStateFlow()

    private val _saveUiState = MutableStateFlow<AuthUiState>(AuthUiState.Idle)
    val saveUiState: StateFlow<AuthUiState> = _saveUiState.asStateFlow()

    init {
        loadData()
    }

    fun loadData() {
        viewModelScope.launch {
            _uiState.value = RiskProfileUiState.Loading

            val optionsResult = getInvestmentProfileOptionsUseCase()
            val profileResult = getCurrentUserProfileUseCase()

            optionsResult.fold(
                onSuccess = { options ->
                    val profile = profileResult.getOrNull()
                    _uiState.value = RiskProfileUiState.Success(
                        options = options,
                        currentProfile = profile
                    )
                },
                onFailure = { error ->
                    _uiState.value = RiskProfileUiState.Error(
                        error.message ?: "Failed to load investment options from backend."
                    )
                }
            )
        }
    }

    fun savePreferences(
        riskTolerance: String?,
        investmentHorizon: String?,
        selectedSectors: List<String>
    ) {
        viewModelScope.launch {
            _saveUiState.value = AuthUiState.Loading

            val request = UpdateProfileRequestDto(
                riskTolerance = riskTolerance,
                investmentHorizon = investmentHorizon,
                sectorPreferences = selectedSectors
            )

            val result = updateUserProfileUseCase(request)
            result.fold(
                onSuccess = { updatedProfile ->
                    val currentState = _uiState.value
                    if (currentState is RiskProfileUiState.Success) {
                        _uiState.value = currentState.copy(currentProfile = updatedProfile)
                    }
                    _saveUiState.value = AuthUiState.Success(
                        message = "Investment preferences successfully updated!"
                    )
                },
                onFailure = { error ->
                    _saveUiState.value = AuthUiState.Error(
                        error.message ?: "Failed to save preferences. Please try again."
                    )
                }
            )
        }
    }

    fun resetSaveState() {
        _saveUiState.value = AuthUiState.Idle
    }
}
