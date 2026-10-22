package com.fyp.basarattradeinvest.assistant

import com.fyp.basarattradeinvest.data.mapper.AssistantDtoMapper
import com.fyp.basarattradeinvest.data.remote.api.AssistantApiService
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatRequestDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationCreateDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationMessagesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationUpdateDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantMessageResponseDto
import com.fyp.basarattradeinvest.data.repository.AssistantRepositoryImpl
import com.fyp.basarattradeinvest.domain.model.assistant.MessageRole
import kotlinx.coroutines.runBlocking
import okhttp3.MediaType.Companion.toMediaTypeOrNull
import okhttp3.Request
import okhttp3.ResponseBody
import okhttp3.ResponseBody.Companion.toResponseBody
import okio.Timeout
import org.junit.Assert.assertEquals
import org.junit.Assert.assertNotNull
import org.junit.Assert.assertTrue
import org.junit.Before
import org.junit.Test
import retrofit2.Call
import retrofit2.Callback
import retrofit2.Response
import java.io.IOException

class AssistantModuleUnitTest {

    private class FakeAssistantApiService : AssistantApiService {
        var shouldFail: Boolean = false
        val storedConversations = mutableListOf<AssistantConversationResponseDto>()
        val storedMessages = mutableMapOf<String, MutableList<AssistantMessageResponseDto>>()

        override suspend fun chat(request: AssistantChatRequestDto): Response<AssistantChatResponseDto> {
            if (shouldFail) {
                return Response.error(500, "{\"detail\":\"Internal server error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val convId = request.conversationId ?: "conv-new-1"
            val chatResponse = AssistantChatResponseDto(
                message = "Analysis for ${request.message}: Market conditions are currently bullish.",
                conversationId = convId
            )
            return Response.success(chatResponse)
        }

        override fun chatStream(request: AssistantChatRequestDto): Call<ResponseBody> {
            val sseData = "data: {\"event\":\"start\",\"conversation_id\":\"conv-101\"}\n\n" +
                    "data: {\"event\":\"chunk\",\"chunk\":\"Analysis: \",\"conversation_id\":\"conv-101\"}\n\n" +
                    "data: {\"event\":\"chunk\",\"chunk\":\"Market is bullish.\",\"conversation_id\":\"conv-101\"}\n\n" +
                    "data: {\"event\":\"done\",\"conversation_id\":\"conv-101\",\"full_response\":\"Analysis: Market is bullish.\"}\n\n"
            val body = sseData.toResponseBody("text/event-stream".toMediaTypeOrNull())
            val fail = shouldFail

            return object : Call<ResponseBody> {
                private var executed = false
                private var canceled = false

                override fun execute(): Response<ResponseBody> {
                    check(!executed) { "Call already executed" }
                    executed = true
                    return if (fail) {
                        Response.error(
                            500,
                            "{\"detail\":\"Stream error\"}".toResponseBody("application/json".toMediaTypeOrNull())
                        )
                    } else {
                        Response.success(body)
                    }
                }

                override fun enqueue(callback: Callback<ResponseBody>) {
                    try {
                        callback.onResponse(this, execute())
                    } catch (error: IOException) {
                        callback.onFailure(this, error)
                    }
                }

                override fun isExecuted(): Boolean = executed

                override fun cancel() {
                    canceled = true
                }

                override fun isCanceled(): Boolean = canceled

                override fun clone(): Call<ResponseBody> = chatStream(request)

                override fun request(): Request = Request.Builder().url("http://localhost/").build()

                override fun timeout(): Timeout = Timeout.NONE
            }
        }

        override suspend fun listConversations(limit: Int?, offset: Int?): Response<AssistantConversationListResponseDto> {
            if (shouldFail) {
                return Response.error(500, "{\"detail\":\"Server error\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            return Response.success(
                AssistantConversationListResponseDto(
                    conversations = storedConversations.toList()
                )
            )
        }

        override suspend fun createConversation(request: AssistantConversationCreateDto): Response<AssistantConversationResponseDto> {
            if (shouldFail) {
                return Response.error(400, "{\"detail\":\"Failed to create conversation\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val newConv = AssistantConversationResponseDto(
                id = "conv-${storedConversations.size + 1}",
                userId = "user-123",
                title = request.title ?: "New Chat",
                createdAt = "2026-09-24T10:00:00Z",
                updatedAt = "2026-09-24T10:00:00Z"
            )
            storedConversations.add(newConv)
            return Response.success(newConv)
        }

        override suspend fun getConversation(conversationId: String): Response<AssistantConversationMessagesResponseDto> {
            if (shouldFail) {
                return Response.error(404, "{\"detail\":\"Conversation not found\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val conv = storedConversations.find { it.id == conversationId }
                ?: AssistantConversationResponseDto(
                    id = conversationId,
                    userId = "user-123",
                    title = "Chat $conversationId",
                    createdAt = "2026-09-24T10:00:00Z",
                    updatedAt = "2026-09-24T10:00:00Z"
                )
            val msgs = storedMessages[conversationId] ?: emptyList()
            return Response.success(
                AssistantConversationMessagesResponseDto(
                    conversation = conv,
                    messages = msgs
                )
            )
        }

        override suspend fun updateConversation(
            conversationId: String,
            request: AssistantConversationUpdateDto
        ): Response<AssistantConversationResponseDto> {
            if (shouldFail) {
                return Response.error(400, "{\"detail\":\"Update failed\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            val index = storedConversations.indexOfFirst { it.id == conversationId }
            val updated = AssistantConversationResponseDto(
                id = conversationId,
                userId = "user-123",
                title = request.title,
                createdAt = "2026-09-24T10:00:00Z",
                updatedAt = "2026-09-24T10:05:00Z"
            )
            if (index >= 0) {
                storedConversations[index] = updated
            } else {
                storedConversations.add(updated)
            }
            return Response.success(updated)
        }

        override suspend fun deleteConversation(conversationId: String): Response<Unit> {
            if (shouldFail) {
                return Response.error(404, "{\"detail\":\"Not found\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            storedConversations.removeAll { it.id == conversationId }
            storedMessages.remove(conversationId)
            return Response.success(Unit)
        }

        override suspend fun regenerateResponse(conversationId: String): Response<AssistantChatResponseDto> {
            if (shouldFail) {
                return Response.error(500, "{\"detail\":\"Regeneration failed\"}".toResponseBody("application/json".toMediaTypeOrNull()))
            }
            return Response.success(
                AssistantChatResponseDto(
                    message = "Regenerated analysis: Momentum indicators point to a strong consolidation phase.",
                    conversationId = conversationId
                )
            )
        }
    }

    private lateinit var fakeApiService: FakeAssistantApiService
    private lateinit var repository: AssistantRepositoryImpl

    @Before
    fun setUp() {
        fakeApiService = FakeAssistantApiService()
        repository = AssistantRepositoryImpl(fakeApiService)
    }

    @Test
    fun testAssistantDtoMapper_mapChatResponseDtoToDomain() {
        val dto = AssistantChatResponseDto(
            message = "Buy recommendation for LUCK",
            conversationId = "conv-101"
        )
        val domain = AssistantDtoMapper.mapChatResponseDtoToDomain(dto)

        assertEquals("Buy recommendation for LUCK", domain.message)
        assertEquals("conv-101", domain.conversationId)
    }

    @Test
    fun testAssistantDtoMapper_mapConversationWithMessagesDtoToDomain() {
        val dto = AssistantConversationMessagesResponseDto(
            conversation = AssistantConversationResponseDto(
                id = "conv-1",
                userId = "user-123",
                title = "Cement Sector Analysis",
                createdAt = "2026-09-24T10:00:00Z",
                updatedAt = "2026-09-24T10:30:00Z"
            ),
            messages = listOf(
                AssistantMessageResponseDto(
                    id = "msg-1",
                    conversationId = "conv-1",
                    role = "user",
                    content = "How is LUCK performing today?",
                    createdAt = "2026-09-24T10:00:00Z"
                ),
                AssistantMessageResponseDto(
                    id = "msg-2",
                    conversationId = "conv-1",
                    role = "assistant",
                    content = "LUCK is trading up +2.4% with solid volume.",
                    createdAt = "2026-09-24T10:00:05Z"
                )
            )
        )
        val domain = AssistantDtoMapper.mapConversationWithMessagesDtoToDomain(dto)

        assertEquals("conv-1", domain.conversation.id)
        assertEquals("user-123", domain.conversation.userId)
        assertEquals("Cement Sector Analysis", domain.conversation.title)
        assertEquals(2, domain.messages.size)
        assertEquals(MessageRole.USER, domain.messages[0].role)
        assertEquals(MessageRole.ASSISTANT, domain.messages[1].role)
    }

    @Test
    fun testRepository_SendMessage_Success() = runBlocking {
        val result = repository.sendMessage("What is the trend for OGDC?", null)
        assertTrue(result.isSuccess)
        val chatResult = result.getOrNull()
        assertNotNull(chatResult)
        assertTrue(chatResult!!.message.contains("bullish", ignoreCase = true))
        assertEquals("conv-new-1", chatResult.conversationId)
    }

    @Test
    fun testRepository_ListAndCreateConversations() = runBlocking {
        // Initially empty
        val listBefore = repository.listConversations().getOrNull()
        assertNotNull(listBefore)
        assertTrue(listBefore!!.isEmpty())

        // Create conversation
        val createResult = repository.createConversation("Tech Sector Inquiry")
        assertTrue(createResult.isSuccess)
        val conv = createResult.getOrNull()
        assertNotNull(conv)
        assertEquals("Tech Sector Inquiry", conv!!.title)

        // List again -> should have 1 item
        val listAfter = repository.listConversations().getOrNull()
        assertNotNull(listAfter)
        assertEquals(1, listAfter!!.size)
        assertEquals("Tech Sector Inquiry", listAfter[0].title)
    }

    @Test
    fun testRepository_UpdateAndDeleteConversation() = runBlocking {
        val conv = repository.createConversation("Old Title").getOrNull()!!

        // Update title
        val updated = repository.updateConversationTitle(conv.id, "New Title").getOrNull()
        assertNotNull(updated)
        assertEquals("New Title", updated!!.title)

        // Delete conversation
        val deleteResult = repository.deleteConversation(conv.id)
        assertTrue(deleteResult.isSuccess)

        // List should be empty
        val list = repository.listConversations().getOrNull()!!
        assertTrue(list.isEmpty())
    }

    @Test
    fun testRepository_RegenerateResponse() = runBlocking {
        val result = repository.regenerateResponse("conv-123")
        assertTrue(result.isSuccess)
        val chatResult = result.getOrNull()
        assertNotNull(chatResult)
        assertTrue(chatResult!!.message.contains("Regenerated", ignoreCase = true))
    }

    @Test
    fun testSSEParser_BackendEvents() {
        val repoImpl = repository as AssistantRepositoryImpl

        // 1. Start event
        val startEvent = repoImpl.parseStreamEvent("{\"event\":\"start\",\"conversation_id\":\"conv-xyz\"}")
        assertTrue(startEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Start)
        assertEquals("conv-xyz", (startEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Start).conversationId)

        // 2. Chunk event
        val chunkEvent = repoImpl.parseStreamEvent("{\"event\":\"chunk\",\"chunk\":\"Market is \",\"conversation_id\":\"conv-xyz\"}")
        assertTrue(chunkEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk)
        assertEquals("Market is ", (chunkEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk).chunk)

        // 3. Done event
        val doneEvent = repoImpl.parseStreamEvent("{\"event\":\"done\",\"conversation_id\":\"conv-xyz\",\"full_response\":\"Market is bullish.\"}")
        assertTrue(doneEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Done)
        assertEquals("Market is bullish.", (doneEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Done).fullResponse)

        // 4. Error event
        val errorEvent = repoImpl.parseStreamEvent("{\"event\":\"error\",\"error\":\"AI service timeout\",\"conversation_id\":\"conv-xyz\"}")
        assertTrue(errorEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Error)
        assertEquals("AI service timeout", (errorEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Error).error)
    }

    @Test
    fun testSSEParser_FallbackFormats() {
        val repoImpl = repository as AssistantRepositoryImpl

        // Fallback OpenAI delta format
        val deltaEvent = repoImpl.parseStreamEvent("{\"delta\":{\"content\":\"Delta token\"}}")
        assertTrue(deltaEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk)
        assertEquals("Delta token", (deltaEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk).chunk)

        // Fallback raw string chunk
        val rawEvent = repoImpl.parseStreamEvent("Plain unformatted token")
        assertTrue(rawEvent is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk)
        assertEquals("Plain unformatted token", (rawEvent as com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk).chunk)
    }

    @Test
    fun testRepository_SendMessageStream_Success() = runBlocking {
        val events = mutableListOf<com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent>()
        repository.sendMessageStream("Analyze LUCK").collect { result ->
            assertTrue(result.isSuccess)
            events.add(result.getOrNull()!!)
        }

        assertTrue(events.isNotEmpty())
        assertTrue(events[0] is com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Start)
        val chunks = events.filterIsInstance<com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Chunk>()
        assertEquals(2, chunks.size)
        assertEquals("Analysis: ", chunks[0].chunk)
        assertEquals("Market is bullish.", chunks[1].chunk)

        val done = events.filterIsInstance<com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent.Done>()
        assertEquals(1, done.size)
        assertEquals("Analysis: Market is bullish.", done[0].fullResponse)
    }

    @Test
    fun testRepository_SendMessageStream_Failure() = runBlocking {
        fakeApiService.shouldFail = true
        val results = mutableListOf<Result<com.fyp.basarattradeinvest.domain.model.assistant.AssistantStreamEvent>>()
        repository.sendMessageStream("Analyze LUCK").collect { result ->
            results.add(result)
        }

        assertEquals(1, results.size)
        assertTrue(results[0].isFailure)
    }

    @Test
    fun testAssistantMarkdownFormatter() {
        val raw = "### Market Overview\n**LUCK** is performing well:\n- High volume\n- RSI is 58"
        val formatted = com.fyp.basarattradeinvest.feature.assistant.AssistantMarkdownFormatter.format(raw)
        assertTrue(formatted.toString().contains("Market Overview"))
        assertTrue(formatted.toString().contains("• High volume"))
        assertTrue(formatted.toString().contains("• RSI is 58"))
    }
}
