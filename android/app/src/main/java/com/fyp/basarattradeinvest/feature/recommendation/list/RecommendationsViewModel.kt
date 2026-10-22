package com.fyp.basarattradeinvest.feature.recommendation.list

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.RecommendationsRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.RecommendationsRepository
import com.fyp.basarattradeinvest.domain.usecase.recommendations.GetRecommendationsUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class RecommendationsViewModel(
    private val repository: RecommendationsRepository = RecommendationsRepositoryImpl(),
    private val getRecommendationsUseCase: GetRecommendationsUseCase = GetRecommendationsUseCase(repository)
) : ViewModel() {

    private val _uiState = MutableStateFlow<RecommendationsUiState>(RecommendationsUiState.Loading)
    val uiState: StateFlow<RecommendationsUiState> = _uiState.asStateFlow()

    private var currentRiskProfile: String = "moderate"
    private var currentSector: String? = null

    init {
        loadRecommendations()
    }

    fun loadRecommendations(riskProfile: String = currentRiskProfile, sector: String? = currentSector) {
        currentRiskProfile = riskProfile
        currentSector = sector
        viewModelScope.launch {
            _uiState.value = RecommendationsUiState.Loading

            val result = getRecommendationsUseCase(
                riskProfile = currentRiskProfile,
                sector = currentSector,
                limit = 20
            )

            if (result.isSuccess) {
                val list = result.getOrThrow()
                if (list.isEmpty()) {
                    _uiState.value = RecommendationsUiState.Empty(currentRiskProfile)
                } else {
                    _uiState.value = RecommendationsUiState.Success(
                        recommendations = list,
                        selectedRiskProfile = currentRiskProfile,
                        selectedSector = currentSector
                    )
                }
            } else {
                _uiState.value = RecommendationsUiState.Error(
                    result.exceptionOrNull()?.message ?: "Unable to load stock recommendations"
                )
            }
        }
    }

    fun setRiskProfile(profile: String) {
        if (currentRiskProfile == profile) return
        loadRecommendations(riskProfile = profile, sector = currentSector)
    }

    fun retry() {
        loadRecommendations(currentRiskProfile, currentSector)
    }
}
