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
    enforce_output_safety,
    check_prompt_injection,
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
        cid = conversation_id.strip() if conversation_id and isinstance(conversation_id, str) and conversation_id.strip().lower() not in ("", "null", "undefined", "string", "none") else None
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
            if not (msg.role == "user" and check_prompt_injection(msg.content))
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

        # Classify intent for context gathering
        intent = classify_intent(message)

        # Handle hard unsafe exploits
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
        except Exception as e:
            log.warning("Groq API unavailable (%s), generating grounded context response", e)
            stock_data = context.get("stocks") or []
            if stock_data:
                s_info = stock_data[0]
                sym = s_info.get("symbol", "Stock")
                price = s_info.get("current_price") or s_info.get("ltp") or "N/A"
                chg = s_info.get("change_pct", 0.0)
                sec = s_info.get("sector", "General Market")
                response = (
                    f"### PSX Market Intelligence: {sym}\n"
                    f"- **Sector:** {sec}\n"
                    f"- **Current Quote:** PKR {price} ({chg:+.2f}%)\n"
                    f"- **Quantitative Summary:** Our multi-factor engine monitors technical momentum (RSI/MACD), "
                    f"fundamentals, and machine learning price horizons. Check the Recommendations and Forecast panels for personalized target and stop levels."
                )
            else:
                response = (
                    "Welcome to Basarat AI Investment Assistant. "
                    "You can explore real-time PSX stock quotes, technical indicator breakdowns, "
                    "AI directional forecasts, Shariah compliance screenings, and portfolio risk simulations."
                )

        # Safety: Check output
        response, output_filtered, violation_type = enforce_output_safety(response)
        if output_filtered:
            log.warning("Output safety filtered response for user %s: %s", user_id, violation_type)

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
        cid = conversation_id.strip() if conversation_id and isinstance(conversation_id, str) and conversation_id.strip().lower() not in ("", "null", "undefined", "string", "none") else None
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

        # Classify intent for context gathering
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

        # Build context
        history_messages = await self.get_conversation_messages(
            conversation.id, user_id, limit=MAX_HISTORY_MESSAGES
        )
        history = [
            {"role": msg.role, "content": msg.content}
            for msg in history_messages
            if not (msg.role == "user" and check_prompt_injection(msg.content))
        ]

        user = await self.db.get(User, user_id)
        context_builder = ContextBuilder(self.db, user)
        context = await context_builder.build_context(message, intent, history)
        messages = context_builder.build_messages(context, message, history)

        full_response_chunks = []
        emitted_live = False
        try:
            async for chunk in groq_client.stream_chat_completion(
                messages=messages,
                temperature=0.3,
                max_tokens=800,
            ):
                full_response_chunks.append(chunk)
                emitted_live = True
                yield f"data: {json.dumps({'event': 'chunk', 'chunk': chunk, 'conversation_id': conversation.id})}\n\n"
        except Exception as e:
            log.warning(f"Groq streaming failed or unavailable, falling back to contextual response: {e}")
            stock_info = (context.get("stock") or context.get("stock_info")) if isinstance(context, dict) else None
            m_lower = message.lower()
            
            if stock_info and isinstance(stock_info, dict):
                sym = stock_info.get("symbol", "Stock")
                name = stock_info.get("name") or sym
                price = stock_info.get("current_price") or stock_info.get("ltp") or "N/A"
                chg = stock_info.get("change_pct", 0.0)
                sec = stock_info.get("sector", "General Market")
                pe = stock_info.get("pe_ratio", "N/A")
                forecast_data = stock_info.get("forecast") or {}
                direction = forecast_data.get("direction", "NEUTRAL")
                conf = forecast_data.get("confidence")
                conf_str = f" ({float(conf)*100:.1f}% confidence)" if conf is not None else ""
                
                full_response_chunks = [
                    f"### PSX Market Intelligence: {sym} ({name})\n",
                    f"- **Sector:** {sec}\n",
                    f"- **Current Market Price:** PKR {price} ({chg:+.2f}%)\n",
                    f"- **Valuation (P/E):** {pe}\n",
                    f"- **AI Directional Forecast:** {direction}{conf_str}\n",
                    f"- **Quantitative Trade Guidance:** Always utilize stop-loss levels and check the multi-factor risk/reward score in your Recommendations tab."
                ]
            elif "shariah" in m_lower or "halal" in m_lower or "kmi" in m_lower:
                full_response_chunks = [
                    "### Shariah & Islamic Compliance Screening\n",
                    "- **Screening Criteria:** PSX KMI-30 Shariah compliance requires debt-to-assets < 37%, non-compliant income < 5%, and illiquid assets > 25%.\n",
                    "- **Islamic Banking / Shariah Stocks:** Companies like Meezan Bank (MEBL) and certified Islamic funds operate in full accordance with AAOIFI and SECP Islamic capital market standards.\n",
                    "- **Verification:** Check the Shariah Screener tab in Basarat for real-time compliance badges on any PSX ticker."
                ]
            elif "kse" in m_lower or "market" in m_lower or "index" in m_lower:
                full_response_chunks = [
                    "### PSX KSE-100 Market Overview\n",
                    "- **Market Status:** Active trading & index surveillance.\n",
                    "- **Key Drivers:** Institutional liquidity, monetary policy sentiment, and corporate earnings announcements.\n",
                    "- **Platform Tools:** Use the Screener to filter top gainers/losers, and explore the AI Stock Analysis tab for deep multi-factor insights."
                ]
            elif "portfolio" in m_lower or "risk" in m_lower or "diversif" in m_lower or "volatil" in m_lower:
                full_response_chunks = [
                    "### Portfolio Risk & Allocation Intelligence\n",
                    "- **Diversification Strategy:** Maintain balanced exposure across high-dividend defensive sectors (e.g. Fertilizer, Power) and growth cyclicals (e.g. Commercial Banks, Cement).\n",
                    "- **Risk Management:** Utilize automated Stop-Loss thresholds and ATR volatility buffers calculated in the Forecast module to protect capital against sudden market drawdowns."
                ]
            else:
                full_response_chunks = [
                    "Welcome to Basarat AI Investment Assistant.\n\n",
                    "I provide real-time Pakistan Stock Exchange (PSX) market intelligence, ",
                    "technical momentum indicators, ML-driven price directional forecasts (XGBoost & GRU), ",
                    "and multi-factor portfolio optimization. How can I assist with your investment analysis today?"
                ]

        full_response = "".join(full_response_chunks).strip()

        full_response, output_filtered, violation_type = enforce_output_safety(full_response)
        if output_filtered:
            log.warning("Output safety filtered streamed response for user %s: %s", user_id, violation_type)

        # If fallback was used and not emitted live, stream out the chunks now
        if not emitted_live:
            chunk_size = 64
            for offset in range(0, len(full_response), chunk_size):
                chunk = full_response[offset:offset + chunk_size]
                yield f"data: {json.dumps({'event': 'chunk', 'chunk': chunk, 'conversation_id': conversation.id})}\n\n"

        # Save to database
        await self._save_message(conversation.id, "user", message)
        await self._save_message(conversation.id, "assistant", full_response)

        if conversation.title == "New Conversation":
            title = message[:50] + ("..." if len(message) > 50 else "")
            conversation.title = title

        await self.db.commit()

        yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': full_response, 'safety_filtered': output_filtered})}\n\n"

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
