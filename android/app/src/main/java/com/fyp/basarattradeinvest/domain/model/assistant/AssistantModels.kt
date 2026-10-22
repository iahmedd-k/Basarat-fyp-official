package com.fyp.basarattradeinvest.domain.model.assistant

/**
 * Domain models for the AI Investment Assistant module.
 * Mapped from backend DTOs via AssistantDtoMapper.
 */

/**
 * A conversation with the AI assistant.
 */
data class AssistantConversation(
    val id: String,
    val userId: String,
    val title: String?,
    val createdAt: String,
    val updatedAt: String
)

/**
 * A single message in a conversation (user or assistant).
 */
data class AssistantMessage(
    val id: String,
    val conversationId: String,
    val role: MessageRole,
    val content: String,
    val createdAt: String
)

/**
 * Message role enum matching backend values: "user", "assistant"
 */
enum class MessageRole(val value: String) {
    USER("user"),
    ASSISTANT("assistant");

    companion object {
        fun fromValue(value: String): MessageRole =
            entries.firstOrNull { it.value == value } ?: USER
    }
}

/**
 * Response from sending a chat message (standard REST or regenerate).
 */
data class AssistantChatResult(
    val message: String,
    val conversationId: String
)

/**
 * Full conversation with its message history.
 */
data class AssistantConversationWithMessages(
    val conversation: AssistantConversation,
    val messages: List<AssistantMessage>
)

/**
 * Domain events emitted during real SSE streaming from POST /api/v1/assistant/chat/stream.
 * Matches backend event types: start, chunk, done, error.
 */
sealed interface AssistantStreamEvent {
    data class Start(val conversationId: String?) : AssistantStreamEvent
    data class Chunk(val chunk: String, val conversationId: String? = null) : AssistantStreamEvent
    data class Done(val conversationId: String? = null, val fullResponse: String? = null) : AssistantStreamEvent
    data class Error(val error: String, val conversationId: String? = null) : AssistantStreamEvent
}
