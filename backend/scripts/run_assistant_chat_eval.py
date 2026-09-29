"""Live chat evaluation for the redesigned Basarat assistant."""

from __future__ import annotations

import asyncio
import time


async def main() -> None:
    from sqlalchemy import select

    from app.db.base import async_session_factory
    from app.models.user import User
    from app.services.assistant_service import AssistantService

    async with async_session_factory() as db:
        result = await db.execute(select(User).limit(1))
        user = result.scalars().first()
        if not user:
            raise SystemExit("No user found in DB - cannot run live chat test")

        service = AssistantService(db)
        prompts = [
            "Hi, what can you help me with?",
            "How is the PSX market today?",
            "Give me a quick snapshot of OGDC",
            "Should I buy HBL?",
            "Explain RSI in simple terms",
            "How do I create a portfolio in the app?",
            "Summarize my portfolio",
        ]

        conversation_id = None
        print("=== Basarat assistant live chat ===")
        print(f"user={user.username} model settings will come from env\n")

        for msg in prompts:
            started = time.perf_counter()
            out = await service.process_chat(
                user_id=user.id,
                message=msg,
                conversation_id=conversation_id,
            )
            elapsed = time.perf_counter() - started
            conversation_id = out["conversation_id"]
            reply = out["response"]
            print(f"--- {elapsed:.2f}s | intent={out.get('intent')} | filtered={out.get('safety_filtered')}")
            print(f"USER: {msg}")
            safe_reply = reply[:700].encode("ascii", "replace").decode("ascii")
            print(f"ASSISTANT: {safe_reply}")
            print()
            if len(reply) < 20:
                raise SystemExit(f"Reply too short for: {msg}")
            if "Should I buy" in msg and "can't process" in reply.lower():
                raise SystemExit("Advice question hard-blocked unexpectedly")

        print(f"OK conversation_id={conversation_id}")


if __name__ == "__main__":
    asyncio.run(main())
