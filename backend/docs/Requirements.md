# Basarat — Software Requirements Specification (SRS)
### Trade Recommendation & Assistance System for PSX

**Version:** 1.1 | **Document:** SRS | **Derived from:** Basarat Execution Document §8 (Consolidated Functional & Non-Functional Requirements)

---

## 1. Introduction

This document is the authoritative, consolidated requirements contract for the Basarat system. It is derived **directly** from Section 8 of the Execution Document ("Consolidated Functional & Non-Functional Requirements") and is intentionally **client-agnostic** — every requirement holds identically for the React (web) and Kotlin/Compose (Android) clients because both consume the same single FastAPI backend.

**Traceability rule:** every requirement ID below (FR-x / NFR-x) is referenced by the modules in the Execution Document and by the `Definition of Done` checklists of each module (Section 6). A module is only "Done" when every FR/NFR it touches is demonstrably satisfied.

---

## 2. Functional Requirements

The 19 functional requirements constitute the complete feature set of the system, organized by module domain.

### 2.1 User Management & Onboarding (Module 1)

**FR-1 — Authentication & session management.** The system shall allow user signup and login via email and password with JWT-based session management (access token TTL 15 min, refresh token TTL 7 days with rotation-on-use and revoke-on-logout).

**FR-2 — Risk profile.** The system shall allow users to configure a risk profile (risk tolerance, investment horizon, sector preferences) used to personalize recommendations.

### 2.2 Market Dashboard (Module 2)

**FR-3 — Live indices.** The system shall display live KSE-100, KSE-30, and KMI-30 index values updating in real time.

**FR-4 — Market breadth.** The system shall display a sector heatmap, top gainers/losers, and volume spikes.

### 2.3 Stock Analysis (Module 3)

**FR-5 — Technical indicators.** The system shall compute and display RSI, MACD, Bollinger Bands, SMA, and ADX for any KSE-100 stock.

**FR-6 — Fundamentals.** The system shall display fundamental metrics (EPS, P/E, ROE, D/E, Dividend Yield) per stock.

### 2.4 ML Forecasting & Recommendations (Modules 4–5)

**FR-7 — Forecast.** The system shall forecast short-term price direction (bullish/bearish/sideways) using a GRU model, with a confidence score, across 1D/1W/1M horizons.

**FR-8 — Recommendation signals.** The system shall generate personalized BUY/SELL/HOLD signals with target price and stop-loss.

### 2.5 Portfolio & Risk (Modules 6–7)

**FR-9 — Portfolio tracking.** The system shall allow users to record and track portfolio holdings with real-time P&L.

**FR-10 — Risk metrics.** The system shall compute portfolio-level VaR, CVaR, Sharpe Ratio, and max drawdown.

**FR-11 — Monte Carlo.** The system shall run Monte Carlo simulations against a user's portfolio.

**FR-12 — Stress tests.** The system shall run stress tests against predefined historical shock scenarios.

### 2.6 Intelligence & Awareness (Modules 8–9)

**FR-13 — Sentiment.** The system shall aggregate Pakistani financial news with FinBERT-based sentiment scoring per stock.

**FR-14 — Event calendar.** The system shall maintain an event calendar for earnings, dividends, and SBP policy dates.

**FR-15 — Alerts.** The system shall allow users to configure custom alert rules and receive push/in-app notifications.

### 2.7 Community & Compliance (Modules 10–11)

**FR-16 — Community.** The system shall provide a community feed for posting and liking trade ideas, with basic moderation (leaderboard deferred).

**FR-17 — Shariah screener.** The system shall screen any KSE-100 stock against AAOIFI/SECP Shariah criteria with a compliance score and purification calculator.

### 2.8 Assistant & Parity (Module 12 + cross-cutting)

**FR-18 — AI assistant.** The system shall provide a conversational AI assistant answering natural-language queries grounded in the user's live data.

**FR-19 — Full parity.** All modules shall be available with functional parity on both Android and Web clients.

> **Consistency interpretation of FR-19 (from Execution Document §8):** identical data for identical API responses — no platform-specific business logic or divergent data rendering.

---

## 3. Non-Functional Requirements

| ID | Category | Requirement |
|---|---|---|
| **NFR-1** | Performance | Dashboard first paint < 2s; live tick delivery < 1s end-to-end. |
| **NFR-2** | Performance | Compute-heavy operations (Monte Carlo, model inference) must not block the UI thread on any client. |
| **NFR-3** | Security | Passwords hashed (bcrypt); JWT access tokens short-lived; refresh tokens rotated and revocable. |
| **NFR-4** | Security | All endpoints require authentication except signup/login/forgot-password. |
| **NFR-5** | Reliability | WebSocket disconnects must fall back gracefully to REST polling. |
| **NFR-6** | Scalability | Backend stateless where possible (session state in Redis, not in-process) to allow horizontal scaling later. |
| **NFR-7** | Usability | Every AI-generated number (forecast, recommendation, risk metric) must show a confidence/methodology indicator — never presented as guaranteed fact. |
| **NFR-8** | Compliance | Explicit in-app disclaimer that the system is not a licensed investment advisor (per SECP and the proposal's stated limitation). |
| **NFR-9** | Data quality | Scraping pipelines must handle source downtime/format changes without crashing the whole ingestion job. |
| **NFR-10** | Consistency | Android and Web must render identical data for identical API responses — no platform-specific business logic. |

---

## 4. Requirements Traceability Matrix (RTM)

Maps functional requirements to the modules (and their Definition of Done) that own them.

| FR | Module(s) | Client screens | Key verification (Module DoD) |
|---|---|---|---|
| FR-1 | 1 — User Mgmt | Login, Signup, Profile | JWT refresh rotation + logout blacklist verified; rate-limit → 429 |
| FR-2 | 1 — User Mgmt | Risk Profile Onboarding | Risk profile persists; consumed by M5/M7 |
| FR-3 | 2 — Market Dashboard | Dashboard/heatmap | Live ticks <1s via WS; REST fallback after 3 failures |
| FR-4 | 2 — Market Dashboard | Gainers/Losers/Spikes | Matches real data on both clients (screenshot-diff) |
| FR-5 | 3 — Stock Analysis | Stock Detail chart tab | Indicator math vs TradingView within tolerance |
| FR-6 | 3 — Stock Analysis | Stock Detail fundamentals tab | Fundamentals sourced from published filings |
| FR-7 | 4 — ML Forecasting | Forecast screen | Baseline accuracy honestly reported; <500ms inference |
| FR-8 | 5 — Recommendation | Recommendations list/detail | Explainable why; deterministic given cached inputs |
| FR-9 | 6 — Portfolio | Portfolio overview, holding detail | P&L recalculates on every tick without reload |
| FR-10 | 7 — Risk & Sentiment | Risk dashboard | VaR/CVaR method documented (parametric vs historical) |
| FR-11 | 7 — Risk & Sentiment | Monte Carlo screen | Async job, non-blocking; distribution + p5/p50/p95 |
| FR-12 | 7 — Risk & Sentiment | Stress test cards | 2008-crash + PKR devaluation scenarios |
| FR-13 | 8 — News & Events | News feed/detail, sentiment badge | FinBERT scores; article summaries only (ToS) |
| FR-14 | 8 — News & Events | Events calendar | Earnings + SBP dates correct at demo time |
| FR-15 | 9 — Alerts | Alert rules, notification center | Rule → trigger → FCM push → deep-link end-to-end |
| FR-16 | 10 — Community | Feed, post detail, leaderboard | Optimistic vote updates + moderation queue |
| FR-17 | 11 — Shariah | Screener, purification, KMI-30 | Thresholds match cited AAOIFI/SECP standard |
| FR-18 | 12 — Assistant | Assistant chat, history | Grounded answers — no hallucinated numbers |
| FR-19 | All | All parity screens | Identical render on Android + Web for same payload |

---

## 5. Acceptance Criteria (Definition of "Done" — system level)

A build is release-worthy only when *all* of the following hold:

- [ ] **FR-1 .. FR-19**: every functional requirement is implemented and demonstrable on **both** clients against the shared backend.
- [ ] **NFR-1**: dashboard first paint < 2s and live tick delivery < 1s measured on a reference device.
- [ ] **NFR-7**: every AI-generated number carries a confidence/methodology indicator — verified by walking the Forecast, Recommendation, Risk, and Assistant screens.
- [ ] **NFR-8**: the non-licensed-advisor disclaimer is present and reachable in-app on both clients.
- [ ] **NFR-9**: a deliberately killed news source does not crash the scraping worker (verified with a fault-injection test).
- [ ] GRU model reports an honest baseline accuracy on held-out PSX data (documented in the FYP report).
- [ ] Shariah thresholds and purification formula match cited AAOIFI/SECP standards (verifiable, not guessed).

---

## 6. Scope Boundaries

**In scope:** all 12 modules fully implemented for both clients, per the Module specs in Execution Document §6.

**Out of scope (deliberately excluded for this FYP):**
- Production/cloud deployment and CI/CD deploy pipeline.
- Self-hosting of an LLM (the AI Assistant uses a hosted API via LangChain).
- Full copyrighted news article bodies (summaries + source links only, per ToS).
- Acting as a licensed/advisory service (system is explicitly non-advisory).

---
*Derived from the Basarat Execution Document v1.1 — Section 8 (Consolidated Functional & Non-Functional Requirements).*
