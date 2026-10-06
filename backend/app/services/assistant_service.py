"""Basarat Stock AI Assistant orchestration service."""

from __future__ import annotations

import json
import logging
from typing import AsyncGenerator, Optional

from sqlalchemy import select, desc
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import get_settings
from app.core.exceptions import NotFoundError
from app.models.assistant import AssistantConversation, AssistantMessage
from app.models.user import User
from app.services.assistant_context import ContextBuilder
from app.services.assistant_safety import (
    classify_intent,
    enforce_output_safety,
    check_prompt_injection,
)
from app.services.groq_client import groq_client

log = logging.getLogger(__name__)

# Lean history window for free-tier token budgets + lower latency
MAX_HISTORY_MESSAGES = 8
CHAT_TEMPERATURE = 0.55
CHAT_MAX_TOKENS = 700
STREAM_MAX_TOKENS = 800


class AssistantService:
    """Main service for the Stock AI Assistant."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.settings = get_settings()

    async def create_conversation(
        self,
        user_id: str,
        title: Optional[str] = None,
    ) -> AssistantConversation:
        conversation = AssistantConversation(
            user_id=user_id,
            title=title or "New Conversation",
        )
        self.db.add(conversation)
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def get_conversation(
        self,
        conversation_id: str,
        user_id: str,
    ) -> AssistantConversation:
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
        result = await self.db.execute(
            select(AssistantConversation)
            .where(AssistantConversation.user_id == user_id)
            .order_by(desc(AssistantConversation.updated_at))
            .limit(limit)
            .offset(offset)
        )
        return list(result.scalars().all())

    async def get_conversation_messages(
        self,
        conversation_id: str,
        user_id: str,
        limit: int = 100,
    ) -> list[AssistantMessage]:
        await self.get_conversation(conversation_id, user_id)
        result = await self.db.execute(
            select(AssistantMessage)
            .where(AssistantMessage.conversation_id == conversation_id)
            .order_by(AssistantMessage.created_at)
            .limit(limit)
        )
        return list(result.scalars().all())

    async def update_conversation_title(
        self,
        conversation_id: str,
        user_id: str,
        title: str,
    ) -> AssistantConversation:
        conversation = await self.get_conversation(conversation_id, user_id)
        conversation.title = title
        await self.db.commit()
        await self.db.refresh(conversation)
        return conversation

    async def delete_conversation(self, conversation_id: str, user_id: str) -> None:
        conversation = await self.get_conversation(conversation_id, user_id)
        await self.db.delete(conversation)
        await self.db.commit()

    def _normalize_conversation_id(self, conversation_id: Optional[str]) -> Optional[str]:
        if not conversation_id or not isinstance(conversation_id, str):
            return None
        cid = conversation_id.strip()
        if cid.lower() in ("", "null", "undefined", "string", "none"):
            return None
        return cid

    async def _resolve_conversation(
        self,
        user_id: str,
        conversation_id: Optional[str],
    ) -> AssistantConversation:
        cid = self._normalize_conversation_id(conversation_id)
        if cid:
            try:
                return await self.get_conversation(cid, user_id)
            except NotFoundError:
                return await self.create_conversation(user_id)
        return await self.create_conversation(user_id)

    async def _load_history(self, conversation_id: str, user_id: str) -> list[dict]:
        history_messages = await self.get_conversation_messages(
            conversation_id, user_id, limit=MAX_HISTORY_MESSAGES
        )
        # Keep only the most recent window (messages come oldest-first)
        window = history_messages[-MAX_HISTORY_MESSAGES:]
        return [
            {"role": msg.role, "content": msg.content}
            for msg in window
            if not (msg.role == "user" and check_prompt_injection(msg.content))
        ]

    @staticmethod
    def _blocked_response() -> str:
        return (
            "I can't process that request. Ask me about PSX stocks, your portfolio, "
            "forecasts, financial concepts, or Basarat app features."
        )

    def _grounded_fallback(self, message: str, context: dict) -> str:
        """Plain-text fallback when Groq is unavailable — still useful, never markdown."""
        stock = context.get("stock") if isinstance(context, dict) else None
        market = context.get("market") if isinstance(context, dict) else None
        portfolio = context.get("portfolio") if isinstance(context, dict) else None
        m_lower = message.lower()

        if isinstance(stock, dict):
            sym = stock.get("symbol", "Stock")
            name = stock.get("name") or sym
            price = stock.get("current_price")
            chg = stock.get("change_pct")
            sector = stock.get("sector") or "n/a"
            forecast = stock.get("forecast") or {}
            direction = forecast.get("direction") or "unavailable"
            lines = [
                f"{sym} ({name}) — retrieved live snapshot:",
                f"- Sector: {sector}",
                f"- Price: PKR {price} ({chg}% change)" if price is not None else "- Price: unavailable",
                f"- Model forecast direction: {direction}",
            ]
            if stock.get("quote_is_stale"):
                lines.append("- Note: quote may be stale.")
            lines.append(
                "The AI model is briefly unavailable, so this is a data snapshot only. "
                "Ask again shortly for a full explanation."
            )
            return "\n".join(lines)

        if portfolio and isinstance(portfolio, dict):
            s = portfolio.get("summary") or {}
            return (
                f"Portfolio snapshot (model temporarily unavailable):\n"
                f"- Value: {s.get('value')}\n"
                f"- P&L: {s.get('pnl')} ({s.get('pnl_pct')}%)\n"
                f"- Holdings: {s.get('holdings_count')}\n"
                "Try again in a moment for a full narrative analysis."
            )

        if market and isinstance(market, dict) or any(k in m_lower for k in ("market", "kse", "index", "psx")):
            breadth = (market or {}).get("breadth") if isinstance(market, dict) else None
            if breadth:
                return (
                    f"PSX breadth snapshot: {breadth.get('advancing')} advancing, "
                    f"{breadth.get('declining')} declining across {breadth.get('symbols_count')} symbols. "
                    "Full commentary is temporarily unavailable — please retry shortly."
                )
            return (
                "Market overview is temporarily limited because the language model is unavailable. "
                "Check the Market tab for live indices, or retry this chat in a moment."
            )

        if any(k in m_lower for k in ("shariah", "halal", "kmi", "islamic")):
            return (
                "Shariah screening in Basarat uses KMI-style filters (debt, non-compliant income, "
                "illiquid assets). Open the Shariah screener for live badges, or retry chat shortly "
                "for a guided explanation."
            )

        return (
            "I'm Basarat Assistant for PSX stocks, portfolios, forecasts, and app help. "
            "The language model is temporarily unavailable — please try again in a few seconds."
        )

    async def process_chat(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
        *,
        skip_save_user: bool = False,
    ) -> dict:
        conversation = await self._resolve_conversation(user_id, conversation_id)
        history = await self._load_history(conversation.id, user_id)

        if check_prompt_injection(message):
            log.warning("Prompt injection detected from user %s", user_id)
            safe_response = self._blocked_response()
            if not skip_save_user:
                await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            return {
                "response": safe_response,
                "conversation_id": conversation.id,
                "blocked": True,
            }

        intent = classify_intent(message)
        if intent == "unsafe":
            log.warning("Unsafe request from user %s: %s", user_id, message[:100])
            safe_response = self._blocked_response()
            if not skip_save_user:
                await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            return {
                "response": safe_response,
                "conversation_id": conversation.id,
                "blocked": True,
            }

        user = await self.db.get(User, user_id)
        context_builder = ContextBuilder(self.db, user)
        context = await context_builder.build_context(message, intent, history)
        messages = context_builder.build_messages(context, message, history)

        try:
            response = await groq_client.chat_completion(
                messages=messages,
                temperature=CHAT_TEMPERATURE,
                max_tokens=CHAT_MAX_TOKENS,
            )
        except Exception as e:
            log.warning("Groq unavailable (%s); using grounded fallback", e)
            response = self._grounded_fallback(message, context)

        response, output_filtered, violation_type = enforce_output_safety(response)
        if output_filtered:
            log.warning("Output safety adjusted response for user %s: %s", user_id, violation_type)

        if not skip_save_user:
            await self._save_message(conversation.id, "user", message)
        await self._save_message(conversation.id, "assistant", response)

        if conversation.title == "New Conversation":
            conversation.title = message[:50] + ("..." if len(message) > 50 else "")

        await self.db.commit()
        return {
            "response": response,
            "conversation_id": conversation.id,
            "intent": intent,
            "safety_filtered": output_filtered,
        }

    async def process_chat_stream(
        self,
        user_id: str,
        message: str,
        conversation_id: Optional[str] = None,
    ) -> AsyncGenerator[str, None]:
        """
        SSE stream. Chunks may stream live for latency; `done.full_response` is always
        the safety-checked final text. If live text was replaced, `replaced` is true.
        """
        conversation = await self._resolve_conversation(user_id, conversation_id)
        yield f"data: {json.dumps({'event': 'start', 'conversation_id': conversation.id})}\n\n"

        if check_prompt_injection(message) or classify_intent(message) == "unsafe":
            safe_response = self._blocked_response()
            await self._save_message(conversation.id, "user", message)
            await self._save_message(conversation.id, "assistant", safe_response)
            await self.db.commit()
            yield f"data: {json.dumps({'event': 'chunk', 'chunk': safe_response, 'conversation_id': conversation.id})}\n\n"
            yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': safe_response, 'blocked': True})}\n\n"
            return

        intent = classify_intent(message)
        history = await self._load_history(conversation.id, user_id)
        user = await self.db.get(User, user_id)
        context_builder = ContextBuilder(self.db, user)
        context = await context_builder.build_context(message, intent, history)
        messages = context_builder.build_messages(context, message, history)

        live_chunks: list[str] = []
        emitted_live = False
        try:
            async for chunk in groq_client.stream_chat_completion(
                messages=messages,
                temperature=CHAT_TEMPERATURE,
                max_tokens=STREAM_MAX_TOKENS,
            ):
                live_chunks.append(chunk)
                emitted_live = True
                yield f"data: {json.dumps({'event': 'chunk', 'chunk': chunk, 'conversation_id': conversation.id})}\n\n"
        except Exception as e:
            log.warning("Groq streaming failed (%s); grounded fallback", e)
            live_chunks = [self._grounded_fallback(message, context)]

        raw = "".join(live_chunks).strip()
        full_response, output_filtered, violation_type = enforce_output_safety(raw)
        if output_filtered:
            log.warning("Stream output safety adjusted for user %s: %s", user_id, violation_type)

        replaced = emitted_live and full_response != raw
        if not emitted_live:
            # Fake-stream fallback so Android still gets progressive UX
            for offset in range(0, len(full_response), 56):
                chunk = full_response[offset:offset + 56]
                yield f"data: {json.dumps({'event': 'chunk', 'chunk': chunk, 'conversation_id': conversation.id})}\n\n"
        elif replaced:
            yield f"data: {json.dumps({'event': 'replace', 'conversation_id': conversation.id, 'full_response': full_response})}\n\n"

        await self._save_message(conversation.id, "user", message)
        await self._save_message(conversation.id, "assistant", full_response)

        if conversation.title == "New Conversation":
            conversation.title = message[:50] + ("..." if len(message) > 50 else "")

        await self.db.commit()
        yield f"data: {json.dumps({'event': 'done', 'conversation_id': conversation.id, 'full_response': full_response, 'safety_filtered': output_filtered, 'replaced': replaced, 'intent': intent})}\n\n"

    async def _save_message(
        self,
        conversation_id: str,
        role: str,
        content: str,
    ) -> AssistantMessage:
        message = AssistantMessage(
            conversation_id=conversation_id,
            role=role,
            content=content,
        )
        self.db.add(message)
        await self.db.flush()
        return message

    async def regenerate_response(
        self,
        conversation_id: str,
        user_id: str,
    ) -> dict:
        await self.get_conversation(conversation_id, user_id)

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

        return await self.process_chat(
            user_id,
            last_user_msg.content,
            conversation_id,
            skip_save_user=True,
        )

    @staticmethod
    def quick_prompts() -> list[dict]:
        """Suggested chips for Android / web."""
        return [
            {"id": "market_today", "label": "How is the PSX market today?", "message": "How is the PSX market today?"},
            {"id": "my_portfolio", "label": "Summarize my portfolio", "message": "Summarize my portfolio performance"},
            {"id": "explain_rsi", "label": "What is RSI?", "message": "Explain RSI in simple terms"},
            {"id": "ogdc_snapshot", "label": "OGDC snapshot", "message": "Give me a quick snapshot of OGDC"},
            {"id": "forecast_hbl", "label": "HBL forecast", "message": "What does the forecast say for HBL?"},
            {"id": "shariah", "label": "Shariah screening", "message": "How does Shariah screening work in Basarat?"},
            {"id": "create_portfolio", "label": "Create a portfolio", "message": "How do I create a portfolio in the app?"},
            {"id": "risk_profile", "label": "My risk profile", "message": "What is my risk profile and what does it mean?"},
        ]
