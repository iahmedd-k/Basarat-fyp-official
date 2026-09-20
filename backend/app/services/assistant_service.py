import json
import logging
from typing import Optional, AsyncGenerator
from uuid import uuid4

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError, ForbiddenError, ServiceUnavailableError
from app.db.session import get_db
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.user import User

from app.services.groq_client import groq_client, GroqError
from app.services.assistant_context import ContextBuilder
from app.services.assistant_safety import (
    classify_intent,
    check_output_safety,
    sanitize_response,
    check_prompt_injection,
    get_safety_response,
)

log = logging.getLogger(__name__)

# Conversation history window
MAX_HISTORY_MESSAGES = 20

# System prompt for the assistant
SYSTEM_PROMPT = """You are the AI assistant for Basarat, a PSX (Pakistan Stock Exchange) stock-market application.

Your purpose is to help users understand financial information, stock-market data, portfolios, forecasts, and application features.

You provide educational information and decision-support analysis.

You do NOT make personalized investment decisions.

Never tell a user to buy, sell, hold, avoid, or allocate a specific amount of money to a security.

Do not provide personalized entry or exit instructions.

When a user asks for a direct investment decision, do not simply refuse. Redirect the user toward useful analysis and explain the relevant factors that they can consider.

Use the user's profile and portfolio only when relevant.

Never invent stock prices, forecasts, holdings, portfolio values, market statistics, or other financial data.

Treat model forecasts as probabilistic model outputs, not guarantees.

Clearly distinguish:
- factual data
- historical information
- model predictions
- general financial education
- uncertainty

Only answer questions within the application's supported scope.

For unrelated questions, politely explain that the assistant is focused on stocks, portfolios, financial education, and the application.

Protect user data and never expose another user's information.

The user makes the final investment decision."""


class AssistantService:
    """Main service for the Stock AI Assistant."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    # ─────────────────────────────────────────────────────────────────
    # Conversation Management
    # ─────────────────────────────────────────────────────────────────

    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
    ) -> AssistantConversation:
        """Create a new conversation."""
        conversation = AssistantConversation(
            user_id=user_id,
            title=title or "New Conversation",
        )
        self.db.add(conversation)
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> AssistantConversation:
        """Get a conversation by ID, verifying ownership."""
        result = await self.db.execute(
            select(AssistantConversation).where(
                AssistantConversation.id == conversation_id,
                AssistantConversation.user_id == user_id,
            )
        )
        conversation = result.scalars().first()
        if not conversation:
            raise NotFoundError("Conversation not found")
        return conversation

    async def list_conversations(
        self,
        user_id: str,
        limit: int = 50,
        offset: int = 0,
    ) -> list[AssistantConversation]:
        """List user's conversations."""
        result = await self.db.execute(
            select(AssistantConversation)
            .where(AssistantConversation.user_id == user_id)
            .order_by(desc(AssistantConversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def update_conversation_title(
        self,
        conversation_id: str,
        user_id: str,
        title: str,
    ) -> AssistantConversation:
        """Update conversation title."""
        conversation = await self.get_conversation(conversation_id, user_id)
        conversation.title = title
        await self.db.flush()
        await self.db.refresh(conversation)
        return conversation

    async def delete_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> None:
        """Delete a conversation."""
        conversation = await self.get_conversation(conversation_id, user_id)
        await self.db.delete(conversation)
        await self.db.flush()

    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
    ) -> list[AssistantMessage]:
        """Get messages for a conversation."""
        # Verify ownership first
        await self.get_conversation(conversation_id, user_id)

        result = await self.db.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id)
            .order_by(AssistantMessage.created_at.asc())
            .limit(limit)
        )
        return list(result.scalars().all())

    # ─────────────────────────────────────────────────────────────────
    # Chat Processing
    # ─────────────────────────────────────────────────────────────────

    async def process_chat(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> dict:
        """
        Process a chat message and return the assistant's response.

        Returns dict with: response, conversation_id, message_id
        """
        # Get or create conversation gracefully
        cid = conversation_id.strip() if conversation_id and isinstance(conversation_id, str) and conversation_id.strip() not in ("", "null", "undefined") else None
        if cid:
            try:
                conversation = await self.get_conversation(cid, user_id)
            except NotFoundError:
                conversation = await self.create_conversation(user_id)
        else:
            # Create new conversation with auto-generated title
            conversation = await self.create_conversation(user_id)

        # Get conversation history
        history_messages = await self.get_conversation_messages(
            conversation.id, user_id, limit=MAX_HISTORY_MESSAGES
        )
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_messages
        ]

        # Safety: Check for prompt injection
        if check_prompt_injection(message):
            log.warning(f"Prompt injection detected from user {user_id}")
            safe_response = (
                "I can't process that request. Please ask about stocks, portfolios, "
                "financial concepts, forecasts, or application features."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            return {
                "response": safe_response,
                "conversation_id": conversation.id,
                "blocked": True,
            }

        # Classify intent
        intent = classify_intent(message)

        # Handle special intents
        if intent == "unsafe":
            log.warning(f"Unsafe request from user {user_id}: {message[:100]}")
            safe_response = (
                "I can't process that request. I'm designed to help with PSX stocks, "
                "portfolios, financial concepts, forecasts, and application features."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            return {
                "response": safe_response,
                "conversation_id": conversation.id,
                "blocked": True,
            }

        if intent == "off_topic":
            safe_response = (
                "I'm designed to help with PSX stocks, portfolios, financial concepts, "
                "forecasts, and features of this application. I can't help with "
                "unrelated topics like jokes, games, general knowledge, or programming."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            return {
                "response": safe_response,
                "conversation_id": conversation.id,
            }

        # Build context
        user = await self.db.get(User, user_id)
        context_builder = ContextBuilder(self.db, user)
        context = await context_builder.build_context(message, intent, history)

        # Build messages for Groq
        messages = context_builder.build_messages(context, message, history)

        # Call Groq
        try:
            response = await groq_client.chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            )
        except GroqError as e:
            log.error(f"Groq API error: {e}")
            if e.status_code >= 500:
                raise ServiceUnavailableError("The AI assistant is temporarily unavailable. Please try again later.")
            raise

        # Safety: Check output
        is_safe, violation_type = check_output_safety(response)
        if not is_safe:
            log.warning(f"Output safety violation for user {user_id}: {violation_type}")
            # Try to sanitize
            sanitized = sanitize_response(response)
            is_safe_after, _ = check_output_safety(sanitized)
            if is_safe_after:
                response = sanitized
            else:
                # Use safe fallback
                response = get_safety_response(violation_type)

        # Save messages
        await self._save_message(conversation.id, "user", message)
        await self._save_message(conversation.id, "assistant", response)

        # Update conversation title if it's the first exchange
        if conversation.title == "New Conversation":
            # Generate title from first message
            title = message[:50] + ("..." if len(message) > 50 else "")
            conversation.title = title

        await self.db.commit()

        return {
            "response": response,
            "conversation_id": conversation.id,
        }

    async def process_chat_stream(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        Stream chat response using Server-Sent Events (SSE) format.
        Yields strings formatted as: `data: {...}\n\n`
        """
        # Get or create conversation gracefully
        cid = conversation_id.strip() if conversation_id and isinstance(conversation_id, str) and conversation_id.strip() not in ("", "null", "undefined") else None
        if cid:
            try:
                conversation = await self.get_conversation(cid, user_id)
            except NotFoundError:
                conversation = await self.create_conversation(user_id)
        else:
            conversation = await self.create_conversation(user_id)

        # Notify stream start
        yield f"data: {json.dumps({'event': 'start', 'conversation_id': conversation.id})}\n\n"

        # Check prompt injection
        if check_prompt_injection(message):
            log.warning(f"Prompt injection detected from user {user_id}")
            safe_response = (
                "I can't process that request. Please ask about stocks, portfolios, "
                "financial concepts, forecasts, or application features."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': safe_response, 'conversation_id': conversation.id})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': safe_response, 'blocked': True})}\n\n"
            return

        # Classify intent
        intent = classify_intent(message)

        if intent == "unsafe":
            log.warning(f"Unsafe request from user {user_id}: {message[:100]}")
            safe_response = (
                "I can't process that request. I'm designed to help with PSX stocks, "
                "portfolios, financial concepts, forecasts, and application features."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': safe_response, 'conversation_id': conversation.id})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': safe_response, 'blocked': True})}\n\n"
            return

        if intent == "off_topic":
            safe_response = (
                "I'm designed to help with PSX stocks, portfolios, financial concepts, "
                "forecasts, and features of this application. I can't help with "
                "unrelated topics like jokes, games, general knowledge, or programming."
            )
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': safe_response, 'conversation_id': conversation.id})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': safe_response})}\n\n"
            return

        # Build context
        history_messages = await self.get_conversation_messages(
            conversation.id, user_id, limit=MAX_HISTORY_MESSAGES
        )
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_messages
        ]

        user = await self.db.get(User, user_id)
        context_builder = ContextBuilder(self.db, user)
        context = await context_builder.build_context(message, intent, history)
        messages = context_builder.build_messages(context, message, history)

        # Stream tokens from Groq
        full_response_chunks = []
        try:
            async for chunk in groq_client.stream_chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=500,
            ):
                full_response_chunks.append(chunk)
                yield f"data: {json.dumps({'event': 'chunk', 'chunk': chunk, 'conversation_id': conversation.id})}\n\n"
        except GroqError as e:
            log.error(f"Groq API streaming error: {e}")
            error_msg = "The AI assistant is temporarily unavailable. Please try again later."
            yield f"data: {json.dumps({'event': 'error', 'error': error_msg, 'conversation_id': conversation.id})}\n\n"
            return
        except Exception as e:
            log.exception("Streaming failed unexpectedly: %s", e)
            error_msg = "An unexpected error occurred while streaming response."
            yield f"data: {json.dumps({'event': 'error', 'error': error_msg, 'conversation_id': conversation.id})}\n\n"
            return

        full_response = "".join(full_response_chunks).strip()

        # Output safety check
        is_safe, violation_type = check_output_safety(full_response)
        if not is_safe:
            log.warning(f"Output safety violation for user {user_id}: {violation_type}")
            sanitized = sanitize_response(full_response)
            is_safe_after, _ = check_output_safety(sanitized)
            if is_safe_after:
                full_response = sanitized
            else:
                full_response = get_safety_response(violation_type)

        # Save to database
        await self._save_message(conversation.id, "user", message)
        await self._save_message(conversation.id, "assistant", full_response)

        if conversation.title == "New Conversation":
            title = message[:50] + ("..." if len(message) > 50 else "")
            conversation.title = title

        await self.db.commit()

        yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': full_response})}\n\n"

    async def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> AssistantMessage:
        """Save a message to the database."""
        message = AssistantMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    # ─────────────────────────────────────────────────────────────────
    # Regeneration / Retry
    # ─────────────────────────────────────────────────────────────────

    async def regenerate_response(
        self,
        conversation_id: str,
        user_id: str,
    ) -> dict:
        """Regenerate the last assistant response."""
        conversation = await self.get_conversation(conversation_id, user_id)

        # Get the last user message
        result = await self.db.execute(
            select(AssistantMessage)
            .where(
                AssistantMessage.conversation_id == conversation_id,
                AssistantMessage.role == "user",
            )
            .order_by(desc(AssistantMessage.created_at))
            .limit(1)
        )
        last_user_msg = result.scalars().first()
        if not last_user_msg:
            raise NotFoundError("No user message to regenerate")

        # Delete the last assistant message
        result = await self.db.execute(
            select(AssistantMessage)
            .where(
                AssistantMessage.conversation_id == conversation_id,
                AssistantMessage.role == "assistant",
            )
            .order_by(desc(AssistantMessage.created_at))
            .limit(1)
        )
        last_assistant_msg = result.scalars().first()
        if last_assistant_msg:
            await self.db.delete(last_assistant_msg)
            await self.db.flush()

        # Re-process the user message
        return await self.process_chat(user_id, last_user_msg.content, conversation_id)