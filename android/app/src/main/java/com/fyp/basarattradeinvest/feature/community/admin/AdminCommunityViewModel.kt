package com.fyp.basarattradeinvest.feature.community.admin

import androidx.lifecycle.ViewModel
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.CommunityRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.community.CommunityReport
import com.fyp.basarattradeinvest.domain.repository.CommunityRepository
import kotlinx.coroutines.flow.MutableSharedFlow
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.SharedFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asSharedFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * ViewModel for Admin Community and Moderation Hub.
 */
class AdminCommunityViewModel(
    private val repository: CommunityRepository = CommunityRepositoryImpl()
) : ViewModel() {

    private val _reportsUiState = MutableStateFlow<AdminReportsUiState>(AdminReportsUiState.Loading)
    val reportsUiState: StateFlow<AdminReportsUiState> = _reportsUiState.asStateFlow()

    private val _actionsUiState = MutableStateFlow<ModerationActionsUiState>(AdminReportsUiState.Loading as ModerationActionsUiState)
    val actionsUiState: StateFlow<ModerationActionsUiState> = _actionsUiState.asStateFlow()

    private val _postReviewUiState = MutableStateFlow<AdminPostReviewUiState>(AdminPostReviewUiState.Idle)
    val postReviewUiState: StateFlow<AdminPostReviewUiState> = _postReviewUiState.asStateFlow()

    private val _userMessage = MutableSharedFlow<String>()
    val userMessage: SharedFlow<String> = _userMessage.asSharedFlow()

    var currentFilter: ReportStatusFilter = ReportStatusFilter.ALL
        private set

    init {
        loadReports(ReportStatusFilter.ALL)
        loadModerationActions()
    }

    fun setFilter(filter: ReportStatusFilter) {
        currentFilter = filter
        loadReports(filter)
    }

    fun refreshAll() {
        loadReports(currentFilter)
        loadModerationActions()
    }

    fun loadReports(filter: ReportStatusFilter = currentFilter) {
        currentFilter = filter
        viewModelScope.launch {
            _reportsUiState.value = AdminReportsUiState.Loading
            val result = repository.getAdminReports(
                status = filter.apiValue,
                limit = 50,
                offset = 0
            )
            result.fold(
                onSuccess = { reports ->
                    if (reports.isEmpty()) {
                        _reportsUiState.value = AdminReportsUiState.Empty
                    } else {
                        _reportsUiState.value = AdminReportsUiState.Success(
                            reports = reports,
                            activeFilter = filter
                        )
                    }
                },
                onFailure = { error ->
                    val isForbidden = error is SecurityException || (error.message?.contains("403", ignoreCase = true) == true)
                    val message = if (isForbidden) {
                        "Access Denied. Administrator or Moderator privileges are required."
                    } else {
                        error.message ?: "Failed to load reports."
                    }
                    _reportsUiState.value = AdminReportsUiState.Error(
                        message = message,
                        isForbidden = isForbidden
                    )
                }
            )
        }
    }

    fun loadModerationActions() {
        viewModelScope.launch {
            _actionsUiState.value = ModerationActionsUiState.Loading
            val result = repository.getModerationActions(limit = 50)
            result.fold(
                onSuccess = { actions ->
                    if (actions.isEmpty()) {
                        _actionsUiState.value = ModerationActionsUiState.Empty
                    } else {
                        _actionsUiState.value = ModerationActionsUiState.Success(actions)
                    }
                },
                onFailure = { error ->
                    val isForbidden = error is SecurityException || (error.message?.contains("403", ignoreCase = true) == true)
                    val message = if (isForbidden) {
                        "Access Denied. Administrator or Moderator privileges are required."
                    } else {
                        error.message ?: "Failed to load moderation actions."
                    }
                    _actionsUiState.value = ModerationActionsUiState.Error(
                        message = message,
                        isForbidden = isForbidden
                    )
                }
            )
        }
    }

    fun loadAdminPost(postId: String) {
        viewModelScope.launch {
            _postReviewUiState.value = AdminPostReviewUiState.Loading
            val result = repository.getAdminPost(postId)
            result.fold(
                onSuccess = { post ->
                    _postReviewUiState.value = AdminPostReviewUiState.Success(post)
                },
                onFailure = { error ->
                    _postReviewUiState.value = AdminPostReviewUiState.Error(
                        error.message ?: "Failed to load post for admin review."
                    )
                }
            )
        }
    }

    fun updateReportStatus(reportId: String, newStatus: String, onDone: (() -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.updateReportStatus(reportId, newStatus)
            result.fold(
                onSuccess = {
                    _userMessage.emit("Report marked as $newStatus")
                    loadReports(currentFilter)
                    loadModerationActions()
                    onDone?.invoke()
                },
                onFailure = { error ->
                    _userMessage.emit("Failed to update report: ${error.message}")
                }
            )
        }
    }

    fun deletePost(postId: String, onDone: (() -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.deleteAdminPost(postId)
            result.fold(
                onSuccess = {
                    _userMessage.emit("Post deleted successfully")
                    loadReports(currentFilter)
                    loadModerationActions()
                    onDone?.invoke()
                },
                onFailure = { error ->
                    _userMessage.emit("Failed to delete post: ${error.message}")
                }
            )
        }
    }

    fun restorePost(postId: String, onDone: (() -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.restoreAdminPost(postId)
            result.fold(
                onSuccess = {
                    _userMessage.emit("Post restored to Published status")
                    loadAdminPost(postId)
                    loadReports(currentFilter)
                    loadModerationActions()
                    onDone?.invoke()
                },
                onFailure = { error ->
                    _userMessage.emit("Failed to restore post: ${error.message}")
                }
            )
        }
    }

    fun removePost(postId: String, onDone: (() -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.removeAdminPost(postId)
            result.fold(
                onSuccess = {
                    _userMessage.emit("Post directly removed by moderation")
                    loadAdminPost(postId)
                    loadReports(currentFilter)
                    loadModerationActions()
                    onDone?.invoke()
                },
                onFailure = { error ->
                    _userMessage.emit("Failed to remove post: ${error.message}")
                }
            )
        }
    }

    fun deleteComment(commentId: String, onDone: (() -> Unit)? = null) {
        viewModelScope.launch {
            val result = repository.deleteAdminComment(commentId)
            result.fold(
                onSuccess = {
                    _userMessage.emit("Comment deleted successfully")
                    loadReports(currentFilter)
                    loadModerationActions()
                    onDone?.invoke()
                },
                onFailure = { error ->
                    _userMessage.emit("Failed to delete comment: ${error.message}")
                }
            )
        }
    }
}
