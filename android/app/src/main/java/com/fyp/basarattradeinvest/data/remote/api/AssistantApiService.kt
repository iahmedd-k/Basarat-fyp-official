package com.fyp.basarattradeinvest.data.remote.api

import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationMessagesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationUpdateDto
import okhttp3.ResponseBody
import retrofit2.Call
import retrofit2.Response
import retrofit2.http.Body
import retrofit2.http.DELETE
import retrofit2.http.GET
import retrofit2.http.PATCH
import retrofit2.http.POST
import retrofit2.http.Path
import retrofit2.http.Query
import retrofit2.http.Streaming

/**
 * Retrofit service for AI Assistant endpoints.
 * Source of truth: live OpenAPI at /api/v1/openapi.json
 * All endpoints require Bearer token authentication (HTTPBearer).
 */
interface AssistantApiService {

    // ─── Chat ───

    /**
     * Send a message to the AI assistant (Standard REST).
     * POST /api/v1/assistant/chat
     */
    @POST("api/v1/assistant/chat")
    suspend fun chat(
        @Body request: AssistantChatRequestDto
    ): Response<AssistantChatResponseDto>

    /**
     * Stream AI assistant response (Server-Sent Events).
     * POST /api/v1/assistant/chat/stream
     *
     * Returns raw ResponseBody for SSE parsing.
     * @Streaming prevents Retrofit from buffering the entire response.
     */
    @Streaming
    @retrofit2.http.Headers("Accept: text/event-stream")
    @POST("api/v1/assistant/chat/stream")
    fun chatStream(
        @Body request: AssistantChatRequestDto
    ): Call<ResponseBody>

    // ─── Conversations ───

    /**
     * List user's conversations.
     * GET /api/v1/assistant/conversations
     */
    @GET("api/v1/assistant/conversations")
    suspend fun listConversations(
        @Query("limit") limit: Int? = null,
        @Query("offset") offset: Int? = null
    ): Response<AssistantConversationListResponseDto>

    /**
     * Create a new conversation.
     * POST /api/v1/assistant/conversations
     */
    @POST("api/v1/assistant/conversations")
    suspend fun createConversation(
        @Body request: AssistantConversationCreateDto
    ): Response<AssistantConversationResponseDto>

    /**
     * Get a conversation with messages.
     * GET /api/v1/assistant/conversations/{conversation_id}
     */
    @GET("api/v1/assistant/conversations/{conversation_id}")
    suspend fun getConversation(
        @Path("conversation_id") conversationId: String
    ): Response<AssistantConversationMessagesResponseDto>

    /**
     * Update conversation title.
     * PATCH /api/v1/assistant/conversations/{conversation_id}
     */
    @PATCH("api/v1/assistant/conversations/{conversation_id}")
    suspend fun updateConversation(
        @Path("conversation_id") conversationId: String,
        @Body request: AssistantConversationUpdateDto
    ): Response<AssistantConversationResponseDto>

    /**
     * Delete a conversation.
     * DELETE /api/v1/assistant/conversations/{conversation_id}
     * Returns 204 No Content on success.
     */
    @DELETE("api/v1/assistant/conversations/{conversation_id}")
    suspend fun deleteConversation(
        @Path("conversation_id") conversationId: String
    ): Response<Unit>

    /**
     * Regenerate the last assistant response.
     * POST /api/v1/assistant/conversations/{conversation_id}/regenerate
     */
    @POST("api/v1/assistant/conversations/{conversation_id}/regenerate")
    suspend fun regenerateResponse(
        @Path("conversation_id") conversationId: String
    ): Response<AssistantChatResponseDto>
}
