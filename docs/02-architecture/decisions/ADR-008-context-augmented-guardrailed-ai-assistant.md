# ADR-008: Context-Augmented & Guardrailed Financial AI Assistant

## Status
**Accepted / Implemented**

## Context
Deploying an AI conversational assistant for financial and stock market queries carries significant risks:
1. **Hallucination & Outdated Knowledge:** Base LLMs do not know today's PSX market quotes or the user's personal holdings.
2. **Regulatory & Legal Liability:** Generating direct financial advice without disclaimers can violate regulatory policies.
3. **Prompt Injection & Misuse:** Users may attempt to jailbreak the assistant to exfiltrate system instructions or perform non-financial tasks.

## Decision
Implement a **Multi-Stage Context-Augmented and Guardrailed Architecture**:

1. **High-Speed Inference via Groq Cloud API:**
   - Provider: Groq Cloud API using high-speed LPUs for low-latency token generation (< 500ms time-to-first-token).
   - Primary Model: `openai/gpt-oss-20b` (or `qwen/qwen3.8-27b` fallback).
2. **Dynamic Financial Context Injection (`ContextBuilder`):**
   - Automatically retrieves and compiles the user's active portfolio holdings, watchlists, risk tolerance preferences, and real-time live stock quotes into a structured system prompt context block before LLM invocation.
   - Implements Redis context caching ([assistant_context_cache.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_context_cache.py)) with a 60-second TTL to avoid redundant database reads during rapid multi-turn chats.
3. **Three-Tier Safety & Guardrail System ([assistant_safety.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_safety.py)):**
   - **Tier 1 — Prompt Injection Defense:** Regular expression and heuristic scanners detect system instruction overrides, jailbreak signatures, and role alteration attempts.
   - **Tier 2 — Intent Classification:** Classifies incoming queries into financial vs out-of-scope domains. Off-topic queries receive polite redirection.
   - **Tier 3 — Output Disclaimer Enforcement:** Automatically validates model outputs and appends standardized statutory financial disclaimers ("This analysis is for educational and informational purposes only and does not constitute financial advice.").
4. **SSE Response Streaming:**
   - Implements Server-Sent Events (`POST /api/v1/assistant/chat/stream`) to stream response tokens progressively to frontend clients.

## Alternatives Considered
- **Direct OpenAI API (GPT-4o):** Considered, but Groq provided significantly lower latency on free/commercial tiers with open-weights models.
- **RAG via Vector Database (Pinecone/Chroma):** Evaluated, but dynamic database context injection (structured portfolio/quote injection) was more reliable and deterministic for real-time portfolio arithmetic than vector chunk retrieval.

## Consequences
- **Positive:** Context-aware, highly personalized financial answers; rapid streaming UX; robust protection against prompt injection and regulatory violations.
- **Negative / Trade-off:** System prompt context consumes a portion of the model's token context window.

## Current Implementation
- Service logic in [app/services/assistant_service.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_service.py).
- Context assembly in [app/services/assistant_context.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_context.py).
- Guardrails in [app/services/assistant_safety.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/services/assistant_safety.py).
- Router in [app/api/v1/assistant/chat.py](file:///d:/Ahmed%20Dev/Projects/Basarat-fyp-official/backend/app/api/v1/assistant/chat.py).
