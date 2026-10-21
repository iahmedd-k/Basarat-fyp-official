package com.fyp.basarattradeinvest.data.mapper

import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantChatResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationListResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationMessagesResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantConversationResponseDto
import com.fyp.basarattradeinvest.data.remote.dto.assistant.AssistantMessageResponseDto
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantChatResult
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversation
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantConversationWithMessages
import com.fyp.basarattradeinvest.domain.model.assistant.AssistantMessage
import com.fyp.basarattradeinvest.domain.model.assistant.MessageRole

/**
 * Maps Assistant DTOs to domain models.
 * All field names trace back to the backend OpenAPI specification.
 */
object AssistantDtoMapper {

    fun mapConversationDtoToDomain(dto: AssistantConversationResponseDto): AssistantConversation {
        return AssistantConversation(
            id = dto.id,
            userId = dto.userId,
            title = dto.title,
            createdAt = dto.createdAt,
            updatedAt = dto.updatedAt
        )
    }

    fun mapConversationListDtoToDomain(dto: AssistantConversationListResponseDto): List<AssistantConversation> {
        return dto.conversations.map { mapConversationDtoToDomain(it) }
    }

    fun mapMessageDtoToDomain(dto: AssistantMessageResponseDto): AssistantMessage {
        return AssistantMessage(
            id = dto.id,
            conversationId = dto.conversationId,
            role = MessageRole.fromValue(dto.role),
            content = dto.content,
            createdAt = dto.createdAt
        )
    }

    fun mapConversationWithMessagesDtoToDomain(
        dto: AssistantConversationMessagesResponseDto
    ): AssistantConversationWithMessages {
        return AssistantConversationWithMessages(
            conversation = mapConversationDtoToDomain(dto.conversation),
            messages = dto.messages.map { mapMessageDtoToDomain(it) }
        )
    }

    fun mapChatResponseDtoToDomain(dto: AssistantChatResponseDto): AssistantChatResult {
        return AssistantChatResult(
            message = dto.message,
            conversationId = dto.conversationId
        )
    }
}
