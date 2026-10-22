package com.fyp.basarattradeinvest.feature.community.create

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import com.fyp.basarattradeinvest.domain.usecase.community.CreateCommunityPostUseCase
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

class CreatePostViewModel(
    private val createPostUseCase: CreateCommunityPostUseCase
) : ViewModel() {

    constructor() : this(CommunityRepositoryImpl())

    constructor(repository: CommunityRepository) : this(
        CreateCommunityPostUseCase(repository)
    )

    class Factory(
        private val repository: CommunityRepository = CommunityRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(CreatePostViewModel::class.java)) {
                return CreatePostViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class: ${modelClass.name}")
        }
    }

    private val _uiState = MutableStateFlow<CreatePostUiState>(CreatePostUiState.Idle)
    val uiState: StateFlow<CreatePostUiState> = _uiState.asStateFlow()

    fun resetState() {
        _uiState.value = CreatePostUiState.Idle
    }

    fun submitPost(
        content: String,
        postType: String,
        stockSymbol: String? = null,
        imageBytes: ByteArray? = null,
        imageFileName: String? = null,
        imageMimeType: String? = null
    ) {
        viewModelScope.launch {
            _uiState.value = CreatePostUiState.Submitting
            val result = createPostUseCase(
                content = content,
                postType = postType,
                stockSymbol = stockSymbol,
                imageBytes = imageBytes,
                imageFileName = imageFileName,
                imageMimeType = imageMimeType
            )
            result.fold(
                onSuccess = { post ->
                    _uiState.value = CreatePostUiState.Success(post)
                },
                onFailure = { error ->
                    _uiState.value = CreatePostUiState.Error(
                        error.localizedMessage ?: "Failed to publish post. Please try again."
                    )
                }
            )
        }
    }
}
