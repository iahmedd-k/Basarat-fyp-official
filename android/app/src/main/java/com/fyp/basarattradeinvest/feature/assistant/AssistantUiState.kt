package com.fyp.basarattradeinvest.feature.assistant

import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversation
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantMessage

/**
 * UI state for the Conversation List screen.
 */
sealed interface ConversationListUiState {
    data object Loading : ConversationListUiState
    data class Success(
        val conversations: List<AssistantConversation>,
        val isRefreshing: Boolean = false
    ) : ConversationListUiState
    data object Empty : ConversationListUiState
    data class Error(val message: String) : ConversationListUiState
}

/**
 * UI state for the Chat screen (single conversation).
 */
sealed interface ChatUiState {
    data object Loading : ChatUiState

    data class Active(
        val conversation: AssistantConversation?,
        val messages: List<ChatMessageItem>,
        val streamingContent: String? = null,
        val isSending: Boolean = false,
        val isStreaming: Boolean = false,
        val isRegenerating: Boolean = false,
        val errorMessage: String? = null
    ) : ChatUiState

    data class Error(val message: String) : ChatUiState
}

/**
 * Represents a single item in the chat RecyclerView.
 * Maps from AssistantMessage domain model to presentation-layer display.
 */
data class ChatMessageItem(
    val id: String,
    val isUser: Boolean,
    val content: String,
    val timestamp: String,
    val isStreaming: Boolean = false
)
