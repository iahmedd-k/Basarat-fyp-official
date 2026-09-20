"""Assistant API endpoints."""

import logging
from typing import Optional

from fastapi import APIRouter, Depends, Query, HTTPException, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.core.rate_limiter import limiter
from app.db.session import get_db
from app.models.user import User
from app.schemas.assistant import (
    AssistantChatRequest,
    AssistantChatResponse,
    AssistantConversationResponse,
    AssistantConversationListResponse,
    AssistantConversationCreate,
    AssistantConversationUpdate,
    AssistantConversationMessagesResponse,
    AssistantMessageResponse,
)
from app.services.assistant_service import AssistantService

router = APIRouter()
log = logging.getLogger(__name__)


def get_assistant_service(db: AsyncSession = Depends(get_db)) -> AssistantService:
    return AssistantService(db)


@router.post(
    "/assistant/chat",
    response_model=AssistantChatResponse,
    summary="Send a message to the AI assistant (Standard REST)",
)
@limiter.limit("30/minute")
async def chat(
    request: Request,
    chat_request: AssistantChatRequest,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """
    Send a message to the Stock AI Assistant (Non-streaming).

    The assistant has real-time context on PSX quotes, technicals, fundamentals,
    model forecasts, and portfolio holdings.
    """
    try:
        result = await service.process_chat(
            user_id=user.id,
            message=chat_request.message,
            conversation_id=chat_request.conversation_id,
        )
        return AssistantChatResponse(
            message=result["response"],
            conversation_id=result["conversation_id"],
        )
    except ServiceUnavailableError:
        raise
    except HTTPException:
        raise
    except Exception as e:
        log.exception("Chat failed for user %s", user.id)
        raise ServiceUnavailableError("Failed to process chat message")


@router.post(
    "/assistant/chat/stream",
    summary="Stream AI assistant response (Server-Sent Events)",
)
@limiter.limit("30/minute")
async def chat_stream(
    request: Request,
    chat_request: AssistantChatRequest,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """
    Stream a response from the Stock AI Assistant token-by-token using SSE (text/event-stream).

    SSE Events format:
    - `data: {"event": "start", "conversation_id": "..."}`
    - `data: {"event": "chunk", "chunk": "token", "conversation_id": "..."}`
    - `data: {"event": "done", "conversation_id": "...", "full_response": "..."}`
    - `data: {"event": "error", "error": "...", "conversation_id": "..."}`
    """
    stream_generator = service.process_chat_stream(
        user_id=user.id,
        message=chat_request.message,
        conversation_id=chat_request.conversation_id,
    )
    return StreamingResponse(
        stream_generator,
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )


@router.get(
    "/assistant/conversations",
    response_model=AssistantConversationListResponse,
    summary="List user's conversations",
)
async def list_conversations(
    limit: int = Query(20, ge=1, le=100),
    offset: int = Query(0, ge=0),
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """List the authenticated user's conversations."""
    conversations = await service.list_conversations(
        user_id=user.id,
        limit=limit,
        offset=offset,
    )
    return AssistantConversationListResponse(
        conversations=[
            AssistantConversationResponse.model_validate(c) for c in conversations
        ]
    )


@router.post(
    "/assistant/conversations",
    response_model=AssistantConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create a new conversation",
)
async def create_conversation(
    data: AssistantConversationCreate,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """Create a new conversation."""
    conversation = await service.create_conversation(
        user_id=user.id,
        title=data.title,
    )
    return AssistantConversationResponse.model_validate(conversation)


@router.get(
    "/assistant/conversations/{conversation_id}",
    response_model=AssistantConversationMessagesResponse,
    summary="Get a conversation with messages",
)
async def get_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """Get a conversation with its message history."""
    conversation = await service.get_conversation(conversation_id, user.id)
    messages = await service.get_conversation_messages(conversation_id, user.id)

    return AssistantConversationMessagesResponse(
        conversation=AssistantConversationResponse.model_validate(conversation),
        messages=[AssistantMessageResponse.model_validate(m) for m in messages],
    )


@router.patch(
    "/assistant/conversations/{conversation_id}",
    response_model=AssistantConversationResponse,
    summary="Update conversation title",
)
async def update_conversation(
    conversation_id: str,
    data: AssistantConversationUpdate,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """Update the conversation title."""
    conversation = await service.update_conversation_title(
        conversation_id=conversation_id,
        user_id=user.id,
        title=data.title or "",
    )
    return AssistantConversationResponse.model_validate(conversation)


@router.delete(
    "/assistant/conversations/{conversation_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Delete a conversation",
)
async def delete_conversation(
    conversation_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """Delete a conversation and all its messages."""
    await service.delete_conversation(conversation_id, user.id)


@router.post(
    "/assistant/conversations/{conversation_id}/regenerate",
    response_model=AssistantChatResponse,
    summary="Regenerate the last assistant response",
)
async def regenerate_response(
    conversation_id: str,
    user: User = Depends(get_current_user),
    service: AssistantService = Depends(get_assistant_service),
):
    """Regenerate the last assistant response for a conversation."""
    try:
        result = await service.regenerate_response(conversation_id, user.id)
        return AssistantChatResponse(
            message=result["response"],
            conversation_id=result["conversation_id"],
        )
    except NotFoundError:
        raise
    except ServiceUnavailableError:
        raise
    except Exception as e:
        log.exception("Regenerate failed for conversation %s", conversation_id)
        raise ServiceUnavailableError("Failed to regenerate response")