package com.fyp.basarattradeinvest.data.repository

import com.fyp.basarattradeinvest.data.mapper.AssistantDtoMapper
import com.fyp.basarattradeinvest.data.remote.NetworkClient
import com.fyp.basarattradeinvest.data.remote.api.AssistantApiService
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationUpdateDto
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantChatResult
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversation
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversationWithMessages
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent
import com.fyp.basarattradeinvest.domain.repository.AssistantRepository
import kotlinx.coroutines.CancellationException
import kotlinx.coroutines.CoroutineStart
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.awaitCancellation
import kotlinx.coroutines.coroutineScope
import kotlinx.coroutines.currentCoroutineContext
import kotlinx.coroutines.ensureActive
import kotlinx.coroutines.flow.Flow
import kotlinx.coroutines.flow.flow
import kotlinx.coroutines.flow.flowOn
import kotlinx.coroutines.launch
import kotlinx.coroutines.withContext
import java.io.BufferedReader
import java.io.InputStreamReader
import java.nio.charset.StandardCharsets

/**
 * Repository implementation for the AI Investment Assistant module.
 * Consumes live backend endpoints via Retrofit + OkHttp.
 * SSE streaming uses raw ResponseBody with @Streaming annotation.
 */
class AssistantRepositoryImpl(
    private val apiService: AssistantApiService = NetworkClient.assistantApiService
) : AssistantRepository {

    override suspend fun sendMessage(
        message: String,
        conversationId: String?
    ): Result<AssistantChatResult> = withContext(Dispatchers.IO) {
        try {
            val request = AssistantChatRequestDto(
                message = message,
                conversationId = conversationId
            )
            val response = apiService.chat(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapChatResponseDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override fun sendMessageStream(
        message: String,
        conversationId: String?
    ): Flow<Result<AssistantStreamEvent>> = flow {
        try {
            val request = AssistantChatRequestDto(
                message = message,
                conversationId = conversationId
            )
            val call = apiService.chatStream(request)
            coroutineScope {
                // Keep the underlying HTTP call cancellable after response headers arrive.
                val cancellationWatcher = launch(start = CoroutineStart.UNDISPATCHED) {
                    try {
                        awaitCancellation()
                    } finally {
                        call.cancel()
                    }
                }

                try {
                    val response = call.execute()
                    if (!response.isSuccessful) {
                        val errorBody = response.errorBody()?.use { it.string() }
                        emit(Result.failure(Exception(parseErrorMessage(response.code(), errorBody))))
                        return@coroutineScope
                    }

                    val body = response.body()
                    if (body == null) {
                        emit(Result.failure(Exception("Empty response from server")))
                        return@coroutineScope
                    }

                    body.use { responseBody ->
                        val reader = BufferedReader(
                            InputStreamReader(responseBody.byteStream(), StandardCharsets.UTF_8)
                        )
                        val dataLines = mutableListOf<String>()
                        var eventName: String? = null

                        suspend fun dispatchSseFrame(): Boolean {
                            val data = dataLines.joinToString("\n")
                            val namedEvent = eventName
                            dataLines.clear()
                            eventName = null

                            val streamEvent = when {
                                data.trim() == "[DONE]" -> AssistantStreamEvent.Done()
                                data.isNotEmpty() -> parseStreamEvent(data, namedEvent)
                                namedEvent.equals("done", ignoreCase = true) ||
                                    namedEvent.equals("complete", ignoreCase = true) -> AssistantStreamEvent.Done()
                                else -> null
                            } ?: return false

                            emit(Result.success(streamEvent))
                            return streamEvent is AssistantStreamEvent.Done ||
                                streamEvent is AssistantStreamEvent.Error
                        }

                        try {
                            while (true) {
                                currentCoroutineContext().ensureActive()
                                val line = reader.readLine() ?: break
                                if (line.isEmpty()) {
                                    if (dispatchSseFrame()) break
                                    continue
                                }
                                if (line.startsWith(":")) continue // SSE comment / heartbeat

                                val separator = line.indexOf(':')
                                val field = if (separator >= 0) line.substring(0, separator) else line
                                val rawValue = if (separator >= 0) line.substring(separator + 1) else ""
                                val value = rawValue.removePrefix(" ")
                                when (field) {
                                    "data" -> dataLines += value
                                    "event" -> eventName = value
                                    else -> {
                                        // Also accept a one-line JSON payload from deployments
                                        // that return a final object instead of SSE frames.
                                        if (dataLines.isEmpty() && line.trimStart().startsWith("{")) {
                                            val parsed = parseStreamEvent(line)
                                            if (parsed != null) {
                                                emit(Result.success(parsed))
                                                if (parsed is AssistantStreamEvent.Done ||
                                                    parsed is AssistantStreamEvent.Error
                                                ) break
                                            }
                                        }
                                    }
                                }
                            }

                            // SSE permits a final frame at EOF without a trailing blank line.
                            if (dataLines.isNotEmpty() || eventName != null) dispatchSseFrame()
                        } finally {
                            reader.close()
                        }
                    }
                } finally {
                    cancellationWatcher.cancel()
                }
            }
        } catch (cancelled: CancellationException) {
            throw cancelled
        } catch (e: Exception) {
            currentCoroutineContext().ensureActive()
            emit(Result.failure(Exception(getNetworkErrorMessage(e))))
        }
    }.flowOn(Dispatchers.IO)

    override suspend fun listConversations(
        limit: Int?,
        offset: Int?
    ): Result<List<AssistantConversation>> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.listConversations(limit, offset)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapConversationListDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override suspend fun createConversation(
        title: String?
    ): Result<AssistantConversation> = withContext(Dispatchers.IO) {
        try {
            val request = AssistantConversationCreateDto(title = title)
            val response = apiService.createConversation(request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapConversationDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override suspend fun getConversation(
        conversationId: String
    ): Result<AssistantConversationWithMessages> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.getConversation(conversationId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapConversationWithMessagesDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override suspend fun updateConversationTitle(
        conversationId: String,
        title: String?
    ): Result<AssistantConversation> = withContext(Dispatchers.IO) {
        try {
            val request = AssistantConversationUpdateDto(title = title)
            val response = apiService.updateConversation(conversationId, request)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapConversationDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override suspend fun deleteConversation(
        conversationId: String
    ): Result<Unit> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.deleteConversation(conversationId)
            if (response.isSuccessful || response.code() == 204) {
                Result.success(Unit)
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    override suspend fun regenerateResponse(
        conversationId: String
    ): Result<AssistantChatResult> = withContext(Dispatchers.IO) {
        try {
            val response = apiService.regenerateResponse(conversationId)
            if (response.isSuccessful && response.body() != null) {
                Result.success(AssistantDtoMapper.mapChatResponseDtoToDomain(response.body()!!))
            } else {
                val errorBody = response.errorBody()?.string()
                Result.failure(Exception(parseErrorMessage(response.code(), errorBody)))
            }
        } catch (e: Exception) {
            Result.failure(Exception(getNetworkErrorMessage(e)))
        }
    }

    // ─── SSE Parsing ───

    /**
     * Parses a single SSE data payload line according to the backend specification:
     * - {"event": "start", "conversation_id": "..."}
     * - {"event": "chunk", "chunk": "token", "conversation_id": "..."}
     * - {"event": "done", "conversation_id": "...", "full_response": "..."}
     * - {"event": "error", "error": "...", "conversation_id": "..."}
     * Also supports generic JSON and fallback raw text chunks.
     */
    internal fun parseStreamEvent(data: String, sseEventName: String? = null): AssistantStreamEvent? {
        return try {
            val json = com.google.gson.JsonParser.parseString(data).asJsonObject
            val eventType = if (json.has("event") && !json.get("event").isJsonNull) {
                json.get("event").asString
            } else sseEventName

            val convId = if (json.has("conversation_id") && !json.get("conversation_id").isJsonNull) {
                json.get("conversation_id").asString
            } else null

            when (eventType?.lowercase()) {
                "start" -> AssistantStreamEvent.Start(convId)
                "chunk" -> {
                    val chunkText = when {
                        json.has("chunk") && !json.get("chunk").isJsonNull -> json.get("chunk").asString
                        json.has("content") && !json.get("content").isJsonNull -> json.get("content").asString
                        json.has("text") && !json.get("text").isJsonNull -> json.get("text").asString
                        else -> ""
                    }
                    if (chunkText.isNotEmpty()) AssistantStreamEvent.Chunk(chunkText, convId) else null
                }
                "done" -> {
                    val fullResponse = if (json.has("full_response") && !json.get("full_response").isJsonNull) {
                        json.get("full_response").asString
                    } else null
                    AssistantStreamEvent.Done(convId, fullResponse)
                }
                "error" -> {
                    val errorMsg = if (json.has("error") && !json.get("error").isJsonNull) {
                        json.get("error").asString
                    } else "Streaming error occurred"
                    AssistantStreamEvent.Error(errorMsg, convId)
                }
                else -> {
                    // Fallback for JSON without explicit "event" field
                    when {
                        json.has("chunk") && !json.get("chunk").isJsonNull ->
                            AssistantStreamEvent.Chunk(json.get("chunk").asString, convId)
                        json.has("content") && !json.get("content").isJsonNull ->
                            AssistantStreamEvent.Chunk(json.get("content").asString, convId)
                        json.has("message") && !json.get("message").isJsonNull ->
                            AssistantStreamEvent.Chunk(json.get("message").asString, convId)
                        json.has("text") && !json.get("text").isJsonNull ->
                            AssistantStreamEvent.Chunk(json.get("text").asString, convId)
                        json.has("delta") && json.get("delta").isJsonObject -> {
                            val delta = json.getAsJsonObject("delta")
                            val content = if (delta.has("content") && !delta.get("content").isJsonNull) {
                                delta.get("content").asString
                            } else ""
                            if (content.isNotEmpty()) AssistantStreamEvent.Chunk(content, convId) else null
                        }
                        else -> null
                    }
                }
            }
        } catch (e: Exception) {
            // Not JSON — fallback to treating raw string as a text chunk if non-blank
            if (data.isNotBlank()) {
                when (sseEventName?.lowercase()) {
                    "done", "complete" -> AssistantStreamEvent.Done(fullResponse = data)
                    "error" -> AssistantStreamEvent.Error(data)
                    else -> AssistantStreamEvent.Chunk(data)
                }
            } else {
                null
            }
        }
    }

    // ─── Error Handling ───

    private fun parseErrorMessage(statusCode: Int, errorBody: String?): String {
        return when (statusCode) {
            401 -> "Session expired. Please sign in again."
            403 -> "You don't have access to this feature."
            404 -> "Conversation not found."
            422 -> parseValidationError(errorBody)
            429 -> "Too many requests. Please wait a moment."
            in 500..599 -> "Unable to reach the assistant. Please try again later."
            else -> "Something went wrong (Error $statusCode)."
        }
    }

    private fun parseValidationError(errorBody: String?): String {
        if (errorBody.isNullOrBlank()) return "Invalid request."
        return try {
            val json = com.google.gson.JsonParser.parseString(errorBody).asJsonObject
            val detail = json.getAsJsonArray("detail")
            if (detail != null && detail.size() > 0) {
                val first = detail.get(0).asJsonObject
                first.get("msg")?.asString ?: "Validation error."
            } else {
                json.get("detail")?.asString ?: "Invalid request."
            }
        } catch (e: Exception) {
            "Invalid request."
        }
    }

    private fun getNetworkErrorMessage(e: Exception): String {
        return when (e) {
            is java.net.UnknownHostException -> "No internet connection."
            is java.net.SocketTimeoutException -> "Request timed out. Please try again."
            is java.net.ConnectException -> "Unable to connect to server."
            is javax.net.ssl.SSLException -> "Secure connection failed."
            else -> e.message ?: "An unexpected error occurred."
        }
    }
}
