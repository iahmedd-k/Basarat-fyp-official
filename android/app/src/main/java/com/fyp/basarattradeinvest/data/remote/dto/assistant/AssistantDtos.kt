package com.fyp.basarattradeinvest.data.remote.dto.assistant

import com.google.gson.annotations.SerializedName

/**
 * Assistant DTOs matching backend OpenAPI specification.
 * Source of truth: live OpenAPI at /api/v1/openapi.json
 */

// ─── Request DTOs ───

/**
 * Request body for POST /api/v1/assistant/chat and POST /api/v1/assistant/chat/stream
 * Schema: AssistantChatRequest
 */
data class AssistantChatRequestDto(
    @SerializedName("message")
    val message: String,

    @SerializedName("conversation_id")
    val conversationId: String? = null
)

/**
 * Request body for POST /api/v1/assistant/conversations
 * Schema: AssistantConversationCreate
 */
data class AssistantConversationCreateDto(
    @SerializedName("title")
    val title: String? = null
)

/**
 * Request body for PATCH /api/v1/assistant/conversations/{conversation_id}
 * Schema: AssistantConversationUpdate
 */
data class AssistantConversationUpdateDto(
    @SerializedName("title")
    val title: String? = null
)

// ─── Response DTOs ───

/**
 * Response from POST /api/v1/assistant/chat and POST /api/v1/assistant/conversations/{id}/regenerate
 * Schema: AssistantChatResponse
 * Required: message, conversation_id
 */
data class AssistantChatResponseDto(
    @SerializedName("message")
    val message: String,

    @SerializedName("conversation_id")
    val conversationId: String
)

/**
 * Conversation metadata.
 * Schema: AssistantConversationResponse
 * Required: id, user_id, created_at, updated_at
 * Optional: title (nullable)
 */
data class AssistantConversationResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("user_id")
    val userId: String,

    @SerializedName("title")
    val title: String? = null,

    @SerializedName("created_at")
    val createdAt: String,

    @SerializedName("updated_at")
    val updatedAt: String
)

/**
 * Response from GET /api/v1/assistant/conversations
 * Schema: AssistantConversationListResponse
 * Required: conversations
 */
data class AssistantConversationListResponseDto(
    @SerializedName("conversations")
    val conversations: List<AssistantConversationResponseDto>
)

/**
 * Response from GET /api/v1/assistant/conversations/{conversation_id}
 * Schema: AssistantConversationMessagesResponse
 * Required: messages, conversation
 */
data class AssistantConversationMessagesResponseDto(
    @SerializedName("messages")
    val messages: List<AssistantMessageResponseDto>,

    @SerializedName("conversation")
    val conversation: AssistantConversationResponseDto
)

/**
 * Individual message in a conversation.
 * Schema: AssistantMessageResponse
 * Required: id, conversation_id, role, content, created_at
 * role enum: "user", "assistant"
 */
data class AssistantMessageResponseDto(
    @SerializedName("id")
    val id: String,

    @SerializedName("conversation_id")
    val conversationId: String,

    @SerializedName("role")
    val role: String,

    @SerializedName("content")
    val content: String,

    @SerializedName("created_at")
    val createdAt: String
)
