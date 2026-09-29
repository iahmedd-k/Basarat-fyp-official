"""Manual / CI-friendly chat smoke tests for the redesigned assistant."""

from __future__ import annotations

import asyncio
import time
from typing import Optional

import pytest


@pytest.mark.asyncio
async def test_assistant_chat_smoke_live():
    """
    Live end-to-end chat against configured DB + Groq.
    Skips if auth seed user is unavailable.
    """
    from sqlalchemy import select
    from app.db.base import async_session_factory
    from app.models.user import User
    from app.services.assistant_service import AssistantService
    from app.services.assistant_safety import classify_intent

    # Intent soft-routing sanity (no network)
    assert classify_intent("Hi there") == "general"
    assert classify_intent("Should I buy HBL?") == "personalized_investment_advice"

    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        user: Optional[User] = result.scalars().first()
        if user is None:
            pytest.skip("No user in database for live assistant chat test")

        service = AssistantService(db)
        prompts = [
            "Hi, what can you help me with?",
            "How is the PSX market today?",
            "Give me a quick snapshot of OGDC",
            "Should I buy HBL?",
            "Explain RSI in simple terms",
            "How do I create a portfolio in the app?",
        ]

        conversation_id = None
        timings = []
        for msg in prompts:
            started = time.perf_counter()
            out = await service.process_chat(
                user_id=user.id,
                message=msg,
                conversation_id=conversation_id,
            )
            elapsed = time.perf_counter() - started
            timings.append((msg, elapsed, out.get("intent"), len(out["response"])))
            conversation_id = out["conversation_id"]

            assert out["response"]
            assert len(out["response"]) > 20
            assert conversation_id
            # Advice questions should still produce analysis, not a one-liner refuse
            if "Should I buy" in msg:
                lower = out["response"].lower()
                assert "can't process" not in lower
                assert out.get("intent") == "personalized_investment_advice"

        # Soft latency budget: average under 12s on free tier + remote DB is acceptable;
        # fail hard only if catastrophically slow.
        avg = sum(t for _, t, _, _ in timings) / len(timings)
        assert avg < 25.0, f"Average latency too high: {avg:.1f}s; details={timings}"

        print("\n=== Assistant chat smoke results ===")
        for msg, elapsed, intent, length in timings:
            print(f"  [{elapsed:5.2f}s] intent={intent:28s} chars={length:4d} | {msg}")
        print(f"  avg={avg:.2f}s conversation_id={conversation_id}")


if __name__ == "__main__":
    asyncio.run(test_assistant_chat_smoke_live())
