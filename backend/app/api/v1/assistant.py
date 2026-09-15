import uuid

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.authorization import get_current_user
from app.core.exceptions import NotFoundError, ServiceUnavailableError
from app.db.session import get_db
from app.models.assistant import Conversation, Message
from app.models.user import User
from app.schemas.auth import (
    AssistantChatRequest,
    AssistantChatResponse,
    ConversationDetailResponse,
    ConversationsListResponse,
    ConversationResponse,
    MessageResponse,
    QuickPromptResponse,
    QuickPromptsResponse,
)

router = APIRouter()


@router.post(
    "/assistant/chat",
    response_model=AssistantChatResponse,
    status_code=201,
    summary="Send a message to the AI assistant",
)
async def chat(
    data: AssistantChatRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        if data.conversation_id:
            result = await db.execute(
                select(Conversation).where(
                    Conversation.id == data.conversation_id,
                    Conversation.user_id == user.id,
                )
            )
            conversation = result.scalars().first()
            if conversation is None:
                raise NotFoundError(f"Conversation '{data.conversation_id}' not found.")
        else:
            conversation = Conversation(
                user_id=user.id,
                title=data.message[:100] if data.message else "New Conversation",
            )
            db.add(conversation)
            await db.flush()
            await db.refresh(conversation)

        user_msg = Message(
            conversation_id=conversation.id,
            role="user",
            content=data.message,
        )
        db.add(user_msg)
        await db.flush()

        assistant_msg = Message(
            conversation_id=conversation.id,
            role="assistant",
            content=f"I received your message: {data.message[:200]}",
        )
        db.add(assistant_msg)
        await db.flush()

        return AssistantChatResponse(
            conversation_id=conversation.id,
            message=assistant_msg.content,
            role="assistant",
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Chat failed: {exc}")


@router.get(
    "/assistant/conversations",
    response_model=ConversationsListResponse,
    summary="List user's conversations",
)
async def get_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Conversation)
            .where(Conversation.user_id == user.id)
            .order_by(Conversation.created_at.desc())
        )
        conversations = result.scalars().all()

        items = [
            ConversationResponse(
                id=c.id,
                title=c.title,
                created_at=c.created_at.isoformat() if c.created_at else "",
            )
            for c in conversations
        ]

        return ConversationsListResponse(conversations=items)
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch conversations: {exc}")


@router.get(
    "/assistant/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Get full conversation message history",
)
async def get_conversation_detail(
    conversation_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id,
            )
        )
        conversation = result.scalars().first()
        if conversation is None:
            raise NotFoundError(f"Conversation '{conversation_id}' not found.")

        messages_result = await db.execute(
            select(Message)
            .where(Message.conversation_id == conversation_id)
            .order_by(Message.created_at.asc())
        )
        messages = messages_result.scalars().all()

        return ConversationDetailResponse(
            id=conversation.id,
            title=conversation.title,
            messages=[
                MessageResponse(
                    id=m.id,
                    role=m.role,
                    content=m.content,
                    created_at=m.created_at.isoformat() if m.created_at else "",
                )
                for m in messages
            ],
            created_at=conversation.created_at.isoformat() if conversation.created_at else "",
        )
    except NotFoundError:
        raise
    except Exception as exc:
        raise ServiceUnavailableError(f"Failed to fetch conversation: {exc}")


@router.get(
    "/assistant/quick-prompts",
    response_model=QuickPromptsResponse,
    summary="Get predefined quick prompt suggestions",
)
async def get_quick_prompts(
    user: User = Depends(get_current_user),
):
    prompts = [
        QuickPromptResponse(id="1", text="What is the current price of HBL?", category="stock"),
        QuickPromptResponse(id="2", text="Analyze the technical indicators for OGDC", category="analysis"),
        QuickPromptResponse(id="3", text="What are the top gainers today?", category="market"),
        QuickPromptResponse(id="4", text="Is my portfolio diversified?", category="portfolio"),
        QuickPromptResponse(id="5", text="Explain RSI and how to use it", category="education"),
        QuickPromptResponse(id="6", text="What is the Shariah compliance status of LUCK?", category="shariah"),
    ]
    return QuickPromptsResponse(prompts=prompts)
