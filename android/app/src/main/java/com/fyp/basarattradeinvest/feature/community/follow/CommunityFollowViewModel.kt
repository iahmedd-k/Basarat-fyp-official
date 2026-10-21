package com.fyp.basarattradeinvest.feature.community.follow

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.fyp.basarattradeinvest.domain.usecase.community.GetFollowersUseCase
import com.fyp.basarattradeinvest.domain.usecase.community.GetFollowingUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CommunityFollowViewModel(
    private val getFollowersUseCase: GetFollowersUseCase,
    private val getFollowingUseCase: GetFollowingUseCase
) : ViewModel() {

    private val _uiState = MutableStateFlow<CommunityFollowUiState>(CommunityFollowUiState.Loading)
    val uiState: StateFlow<CommunityFollowUiState> = _uiState.asStateFlow()

    private var currentUserId: String = ""
    private var isFollowingMode: Boolean = false
    private var cursor: String? = null

    fun loadUsers(userId: String, isFollowing: Boolean, isRefresh: Boolean = false) {
        currentUserId = userId
        isFollowingMode = isFollowing

        viewModelScope.launch {
            if (!isRefresh && _uiState.value !is CommunityFollowUiState.Success) {
                _uiState.value = CommunityFollowUiState.Loading
            }

            val result = if (isFollowing) {
                getFollowingUseCase(userId = userId, cursor = null, limit = 20)
            } else {
                getFollowersUseCase(userId = userId, cursor = null, limit = 20)
            }

            if (result.isSuccess) {
                val list = result.getOrNull()!!
                cursor = list.cursor
                if (list.users.isEmpty()) {
                    _uiState.value = CommunityFollowUiState.Empty
                } else {
                    _uiState.value = CommunityFollowUiState.Success(
                        users = list.users,
                        hasMore = list.hasMore,
                        isFollowingMode = isFollowing,
                        isRefreshing = false
                    )
                }
            } else {
                val msg = result.exceptionOrNull()?.message ?: "Unable to load users"
                _uiState.value = CommunityFollowUiState.Error(msg)
            }
        }
    }

    class Factory(
        private val repository: CommunityRepository = CommunityRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(CommunityFollowViewModel::class.java)) {
                return CommunityFollowViewModel(
                    getFollowersUseCase = GetFollowersUseCase(repository),
                    getFollowingUseCase = GetFollowingUseCase(repository)
                ) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}
