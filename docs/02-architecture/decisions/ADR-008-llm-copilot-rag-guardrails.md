# ADR-008: AI Investment Copilot RAG Architecture and Financial Safety Guardrails

## Status
Accepted

## Context
Retail investors need intelligent, conversational assistance to analyze PSX equities, interpret complex technical indicators, and evaluate portfolio risk. However, purely generative Large Language Models (LLMs) suffer from hallucinations, lack real-time local Pakistani market data, and risk making ungrounded financial promises or guarantees without appropriate disclaimers.

## Decision
1. **Groq Cloud Inference Engine**: Utilize Groq’s Llama-3-70B model via high-speed API integration for low latency response times (<500ms initial token latency).
2. **Context-Enriched Retrieval-Augmented Generation (RAG)**: Dynamically inject structured local market data into prompt payloads:
   - Live quotes and daily % change
   - Calculated technical indicators (RSI, MACD, Bollinger Bands, Moving Averages)
   - Fundamental valuation ratios (P/E, P/B, Dividend Yield, Debt/Equity)
   - KMI-30 / AAOIFI Shariah compliance status
   - FinBERT news sentiment trends
3. **Multi-Stage Safety & Guardrails**:
   - **Pre-Inference Guardrails**: Block prompt injection attacks, filter non-financial queries, and enforce ethical bounds.
   - **Post-Inference Guardrails**: Automatically append statutory financial risk disclaimers, verify that responses do not promise guaranteed capital returns, and maintain compliance with SECP advisory guidelines.
4. **Dual Interface**: Expose both standard synchronous JSON endpoints (`/api/v1/assistant/chat`) and streaming Server-Sent Events (`/api/v1/assistant/chat/stream`) for real-time token rendering.

## Consequences
- **Positive**: Accurate, contextually grounded answers reflecting up-to-the-minute PSX stock fundamentals.
- **Positive**: Protects users from reckless financial speculation through mandatory disclaimers.
- **Positive**: Sub-second user interaction speeds on mobile clients.
- **Negative**: Dependent on Groq API uptime and rate limits; fallback models and context caching in Redis are implemented to mitigate upstream throttling.
