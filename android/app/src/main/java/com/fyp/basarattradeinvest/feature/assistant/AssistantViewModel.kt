package com.fyp.basarattradeinvest.feature.assistant

import androidx.lifecycle.ViewModel
import androidx.lifecycle.ViewModelProvider
import androidx.lifecycle.viewModelScope
import com.fyp.basarattradeinvest.data.repository.AssistantRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversation
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantMessage
import com.fyp.basarattradeinvest.domain.model.assistant.MessageRole
import com.fyp.basarattradeinvest.domain.repository.AssistantRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.Job
import kotlinx.coroutines.flow.MutableStateFlow
import kotlinx.coroutines.flow.StateFlow
import kotlinx.coroutines.flow.asStateFlow
import kotlinx.coroutines.launch

/**
 * ViewModel for the AI Investment Assistant module.
 * Manages conversation list, active chat, streaming, and conversation CRUD.
 */
class AssistantViewModel(
    private val repository: AssistantRepository
) : ViewModel() {

    // ─── Conversation List State ───
    private val _conversationListState = MutableStateFlow<ConversationListUiState>(ConversationListUiState.Loading)
    val conversationListState: StateFlow<ConversationListUiState> = _conversationListState.asStateFlow()

    // ─── Chat State ───
    private val _chatState = MutableStateFlow<ChatUiState>(ChatUiState.Loading)
    val chatState: StateFlow<ChatUiState> = _chatState.asStateFlow()

    // Track active streaming job for cancellation
    private var streamingJob: Job? = null

    // Current conversation context
    private var currentConversationId: String? = null

    // ─── Conversation List ───

    fun loadConversations() {
        viewModelScope.launch {
            _conversationListState.value = ConversationListUiState.Loading
            repository.listConversations(limit = 50).fold(
                onSuccess = { conversations ->
                    if (conversations.isEmpty()) {
                        _conversationListState.value = ConversationListUiState.Empty
                    } else {
                        _conversationListState.value = ConversationListUiState.Success(conversations)
                    }
                },
                onFailure = { error ->
                    _conversationListState.value = ConversationListUiState.Error(
                        error.message ?: "Unable to load conversations"
                    )
                }
            )
        }
    }

    fun createNewConversation(title: String? = null) {
        viewModelScope.launch {
            repository.createConversation(title).fold(
                onSuccess = { conversation ->
                    currentConversationId = conversation.id
                    _chatState.value = ChatUiState.Active(
                        conversation = conversation,
                        messages = emptyList()
                    )
                    // Refresh list in background
                    loadConversations()
                },
                onFailure = { error ->
                    _chatState.value = ChatUiState.Error(
                        error.message ?: "Unable to create conversation"
                    )
                }
            )
        }
    }

    fun deleteConversation(conversationId: String) {
        viewModelScope.launch {
            repository.deleteConversation(conversationId).fold(
                onSuccess = {
                    // Remove from list locally
                    val current = _conversationListState.value
                    if (current is ConversationListUiState.Success) {
                        val updated = current.conversations.filter { it.id != conversationId }
                        _conversationListState.value = if (updated.isEmpty()) {
                            ConversationListUiState.Empty
                        } else {
                            current.copy(conversations = updated)
                        }
                    }
                    // If this was the active conversation, clear chat
                    if (currentConversationId == conversationId) {
                        currentConversationId = null
                        _chatState.value = ChatUiState.Loading
                    }
                },
                onFailure = { /* Ignore delete failure silently, list keeps the item */ }
            )
        }
    }

    fun updateConversationTitle(conversationId: String, newTitle: String) {
        viewModelScope.launch {
            repository.updateConversationTitle(conversationId, newTitle).fold(
                onSuccess = { updatedConversation ->
                    // Update in list
                    val current = _conversationListState.value
                    if (current is ConversationListUiState.Success) {
                        val updated = current.conversations.map {
                            if (it.id == conversationId) updatedConversation else it
                        }
                        _conversationListState.value = current.copy(conversations = updated)
                    }
                    // Update in active chat
                    val chatCurrent = _chatState.value
                    if (chatCurrent is ChatUiState.Active && chatCurrent.conversation?.id == conversationId) {
                        _chatState.value = chatCurrent.copy(conversation = updatedConversation)
                    }
                },
                onFailure = { /* Title update failed, UI stays as-is */ }
            )
        }
    }

    // ─── Chat ───

    fun loadConversation(conversationId: String) {
        currentConversationId = conversationId
        viewModelScope.launch {
            _chatState.value = ChatUiState.Loading
            repository.getConversation(conversationId).fold(
                onSuccess = { conversationWithMessages ->
                    _chatState.value = ChatUiState.Active(
                        conversation = conversationWithMessages.conversation,
                        messages = conversationWithMessages.messages.map { it.toChatMessageItem() }
                    )
                },
                onFailure = { error ->
                    _chatState.value = ChatUiState.Error(
                        error.message ?: "Unable to load conversation"
                    )
                }
            )
        }
    }

    /**
     * Opens a fresh chat without an existing conversation.
     * The conversation will be created server-side when the first message is sent.
     */
    fun startNewChat() {
        currentConversationId = null
        _chatState.value = ChatUiState.Active(
            conversation = null,
            messages = emptyList()
        )
    }

    /**
     * Send a message using the real backend SSE streaming endpoint.
     * Progressively updates a single assistant message in the chat list.
     * A stream failure is surfaced instead of automatically resending the message via REST,
     * which could create a duplicate if the server accepted the streamed request.
     */
    fun sendMessage(userMessage: String) {
        val trimmed = userMessage.trim()
        if (trimmed.isEmpty()) return

        val currentState = _chatState.value
        if (currentState !is ChatUiState.Active) return
        if (currentState.isSending || currentState.isStreaming) return // Prevent double-send

        // Add user message optimistically
        val userMsgItem = ChatMessageItem(
            id = "user-${System.currentTimeMillis()}",
            isUser = true,
            content = trimmed,
            timestamp = getCurrentTimestamp()
        )

        // Add a single assistant message in streaming state
        val assistantMsgId = "assistant-stream-${System.currentTimeMillis()}"
        val assistantMsgItem = ChatMessageItem(
            id = assistantMsgId,
            isUser = false,
            content = "",
            timestamp = getCurrentTimestamp(),
            isStreaming = true
        )

        val updatedMessages = currentState.messages + userMsgItem + assistantMsgItem

        _chatState.value = currentState.copy(
            messages = updatedMessages,
            isSending = true,
            isStreaming = true,
            streamingContent = "",
            errorMessage = null
        )

        // Cancel any previous streaming job before starting a new one
        streamingJob?.cancel()
        streamingJob = viewModelScope.launch {
            val accumulated = StringBuilder()
            try {
                repository.sendMessageStream(trimmed, currentConversationId).collect { result ->
                    result.fold(
                        onSuccess = { event ->
                            when (event) {
                                is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Start -> {
                                    if (!event.conversationId.isNullOrBlank()) {
                                        currentConversationId = event.conversationId
                                    }
                                }
                                is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk -> {
                                    if (!event.conversationId.isNullOrBlank() && currentConversationId == null) {
                                        currentConversationId = event.conversationId
                                    }
                                    accumulated.append(event.chunk)
                                    val currentText = accumulated.toString()
                                    updateStreamingMessage(assistantMsgId, currentText, isStreaming = true)
                                }
                                is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Done -> {
                                    if (!event.conversationId.isNullOrBlank() && currentConversationId == null) {
                                        currentConversationId = event.conversationId
                                    }
                                    val finalText = if (!event.fullResponse.isNullOrBlank()) {
                                        event.fullResponse
                                    } else {
                                        accumulated.toString()
                                    }
                                    updateStreamingMessage(assistantMsgId, finalText, isStreaming = false)
                                }
                                is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Error -> {
                                    if (!event.conversationId.isNullOrBlank() && currentConversationId == null) {
                                        currentConversationId = event.conversationId
                                    }
                                    handleStreamError(event.error, assistantMsgId, accumulated.toString())
                                }
                            }
                        },
                        onFailure = { error ->
                            handleStreamError(error.message ?: "Streaming error", assistantMsgId, accumulated.toString())
                        }
                    )
                }

                // Treat EOF without a terminal event as completion if chunks arrived; otherwise
                // leave a visible error instead of a permanent loading indicator.
                val state = _chatState.value
                val assistantStillStreaming = state is ChatUiState.Active &&
                    state.messages.any { it.id == assistantMsgId && it.isStreaming }
                if (assistantStillStreaming) {
                    if (accumulated.isNotEmpty()) {
                        updateStreamingMessage(assistantMsgId, accumulated.toString(), isStreaming = false)
                    } else {
                        handleStreamError(
                            "The response stream ended before a reply arrived. Please try again.",
                            assistantMsgId,
                            ""
                        )
                    }
                }
            } catch (cancelled: CancellationException) {
                throw cancelled
            } catch (error: Exception) {
                handleStreamError(
                    error.message ?: "Streaming error",
                    assistantMsgId,
                    accumulated.toString()
                )
            }
        }
    }

    /**
     * Stop active stream generation safely, preserving all content received so far.
     */
    fun stopGenerating() {
        streamingJob?.cancel()
        streamingJob = null
        val state = _chatState.value
        if (state is ChatUiState.Active && (state.isSending || state.isStreaming)) {
            val updatedMessages = state.messages.map { msg ->
                if (msg.isStreaming) {
                    val finalContent = if (msg.content.isBlank()) "[Generation cancelled]" else msg.content
                    msg.copy(content = finalContent, isStreaming = false)
                } else msg
            }
            _chatState.value = state.copy(
                messages = updatedMessages,
                isSending = false,
                isStreaming = false,
                streamingContent = null
            )
        }
    }

    private fun updateStreamingMessage(messageId: String, content: String, isStreaming: Boolean) {
        val state = _chatState.value
        if (state is ChatUiState.Active) {
            val updatedMessages = state.messages.map { msg ->
                if (msg.id == messageId) {
                    msg.copy(content = content, isStreaming = isStreaming)
                } else msg
            }
            _chatState.value = state.copy(
                messages = updatedMessages,
                isSending = isStreaming,
                isStreaming = isStreaming,
                streamingContent = if (isStreaming) content else null
            )
        }
    }

    private fun handleStreamError(errorMessage: String, messageId: String, receivedText: String) {
        val state = _chatState.value
        if (state is ChatUiState.Active) {
            val updatedMessages = state.messages.map { msg ->
                if (msg.id == messageId) {
                    val content = if (receivedText.isNotBlank()) receivedText else "Unable to complete response."
                    msg.copy(content = content, isStreaming = false)
                } else msg
            }
            _chatState.value = state.copy(
                messages = updatedMessages,
                isSending = false,
                isStreaming = false,
                streamingContent = null,
                errorMessage = errorMessage
            )
        }
    }

    fun regenerateLastResponse() {
        val convId = currentConversationId ?: return
        val currentState = _chatState.value
        if (currentState !is ChatUiState.Active) return
        if (currentState.isRegenerating) return

        _chatState.value = currentState.copy(isRegenerating = true, errorMessage = null)

        viewModelScope.launch {
            repository.regenerateResponse(convId).fold(
                onSuccess = { chatResult ->
                    val state = _chatState.value
                    if (state is ChatUiState.Active) {
                        // Replace last assistant message if it exists
                        val messages = state.messages.toMutableList()
                        val lastAssistantIdx = messages.indexOfLast { !it.isUser }
                        if (lastAssistantIdx >= 0) {
                            messages[lastAssistantIdx] = messages[lastAssistantIdx].copy(
                                content = chatResult.message,
                                timestamp = getCurrentTimestamp()
                            )
                        } else {
                            // No existing assistant message — add new one
                            messages.add(
                                ChatMessageItem(
                                    id = "regen-${System.currentTimeMillis()}",
                                    isUser = false,
                                    content = chatResult.message,
                                    timestamp = getCurrentTimestamp()
                                )
                            )
                        }
                        _chatState.value = state.copy(
                            messages = messages,
                            isRegenerating = false,
                            errorMessage = null
                        )
                    }
                },
                onFailure = { error ->
                    val state = _chatState.value
                    if (state is ChatUiState.Active) {
                        _chatState.value = state.copy(
                            isRegenerating = false,
                            errorMessage = error.message ?: "Failed to regenerate response"
                        )
                    }
                }
            )
        }
    }

    fun dismissError() {
        val state = _chatState.value
        if (state is ChatUiState.Active) {
            _chatState.value = state.copy(errorMessage = null)
        }
    }

    override fun onCleared() {
        super.onCleared()
        streamingJob?.cancel()
    }

    // ─── Helpers ───

    private fun AssistantMessage.toChatMessageItem(): ChatMessageItem {
        return ChatMessageItem(
            id = id,
            isUser = role == MessageRole.USER,
            content = content,
            timestamp = createdAt
        )
    }

    private fun getCurrentTimestamp(): String {
        val sdf = java.text.SimpleDateFormat("yyyy-MM-dd'T'HH:mm:ss'Z'", java.util.Locale.US)
        sdf.timeZone = java.util.TimeZone.getTimeZone("UTC")
        return sdf.format(java.util.Date())
    }

    // ─── Factory ───

    class Factory(
        private val repository: AssistantRepository = AssistantRepositoryImpl()
    ) : ViewModelProvider.Factory {
        @Suppress("UNCHECKED_CAST")
        override fun <T : ViewModel> create(modelClass: Class<T>): T {
            if (modelClass.isAssignableFrom(AssistantViewModel::class.java)) {
                return AssistantViewModel(repository) as T
            }
            throw IllegalArgumentException("Unknown ViewModel class")
        }
    }
}
