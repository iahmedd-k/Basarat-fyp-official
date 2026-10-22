# BASARAT

**AI-Powered Trade Recommendation & Assistance System for Pakistan Stock Exchange (PSX)**

[![Platform](https://img.shields.io/badge/Platform-Android%20Native-3DDC84?logo=android&logoColor=white)](#)
[![Language](https://img.shields.io/badge/Language-Kotlin-7F52FF?logo=kotlin&logoColor=white)](#)
[![Architecture](https://img.shields.io/badge/Architecture-Clean%20%2B%20MVVM-blue)](#)
[![Target SDK](https://img.shields.io/badge/Target%20SDK-35-orange)](#)
[![Min SDK](https://img.shields.io/badge/Min%20SDK-24-informational)](#)
[![Market](https://img.shields.io/badge/Exchange-PSX%20(KSE-100,%20KMI-30)-00B894)](#)

---

## 1. Project Overview

**BASARAT** is a mobile-first financial decision-support platform for investors and traders on the Pakistan Stock Exchange (PSX). It combines quantitative market analysis, machine-learning forecasts, financial news sentiment, Shariah compliance screening, portfolio risk analytics, and community-driven trader insights.

The Android client functions strictly as the **presentation layer**. It consumes processed data and ML predictions via secure REST/WebSocket APIs; it does not perform raw web scraping, model training, or database management on-device.

---

## 2. Features

| Category | Capabilities |
|---|---|
| **Stock Analysis** | Technical indicators (RSI, MACD, Bollinger, SMA, ADX), price history charts, fundamental ratios (P/E, P/B, ROE, EPS, dividend yield) |
| **ML Forecasting** | Deep-learning price forecasts with target price, stop-loss, upside/downside, confidence scoring |
| **Sentiment Analysis** | FinBERT news sentiment, market mood overview, sentiment history charts |
| **Shariah Screening** | KMI-30 compliance, debt & income ratio screening |
| **Portfolio Analytics** | Holdings, transactions, VaR, Sharpe ratio, max drawdown, Monte Carlo risk simulation |
| **Recommendations** | AI stock picks, engine signal breakdown, target/stop levels |
| **Community** | Posts, comments, sentiment-tagged news, moderation hub (admin reports & audit log) |
| **Alerts** | Price alert rules with notification delivery |
| **Live Market** | Real-time PSX tickers via WebSocket, indices, sector performance |

---

## 3. Technology Stack

| Dimension | Technology | Purpose |
|---|---|---|
| Language | Kotlin | Null-safe, coroutine-first development |
| UI | Native Android XML + Material 3 | Strictly XML layouts (no Jetpack Compose) |
| Architecture | Clean Architecture + MVVM | Separation of Presentation / Domain / Data |
| State Management | Kotlin Coroutines + `StateFlow` | Immutable, reactive unidirectional UI state |
| View Binding | Jetpack ViewBinding | Type-safe, null-safe view references |
| Navigation | Jetpack Navigation Component | Single-Activity architecture (`NavHostFragment`) |
| Networking | Retrofit 2 + OkHttp 3 + Gson | REST API consumption & JSON serialization |
| Charting | MPAndroidChart | Candlestick, line, bar charts |
| Async / Push | WorkManager + Firebase Cloud Messaging | Background job scheduling & push notifications |
| Build | Gradle Kotlin DSL | Compile SDK 35, Min SDK 24, Target SDK 35, Java 17 |

---

## 4. Architecture

The codebase follows **Clean Architecture** with a strict one-way dependency rule:

```
feature/  (UI)  -->  domain/  (business logic)  <--  data/  (backend)
```

- **`core/`** — Cross-cutting infrastructure: auth interceptor, token refresh, secure encrypted token storage (Android Keystore), notification channels, WorkManager workers, custom chart views.
- **`domain/`** — Pure Kotlin with **zero Android imports**. Contains domain models, repository interfaces, and use cases. Runs on a bare JVM — all unit tests run without an emulator.
- **`data/`** — Backend integration: Retrofit API interfaces, DTOs, mappers, repository implementations. All network calls run on `Dispatchers.IO` and return `Result<T>`.
- **`feature/`** — 20 UI packages. Each screen follows a 3-file convention: `Fragment` + `ViewModel` + `UiState` (sealed `Loading`/`Success`/`Empty`/`Error` states).

### Data Flow

```
User action
    ↓
Fragment collects ViewModel StateFlow
    ↓
ViewModel orchestrates use cases via viewModelScope
    ↓
Use case calls Repository interface (domain layer)
    ↓
Repository impl calls Retrofit service (data layer)
    ↓
AuthInterceptor attaches Bearer token
    ↓
═════════ HTTP Request to Backend ═════════
        ↓
Gson deserializes JSON → DTO
    ↓
Mapper converts DTO → Domain model
    ↓
Result<T> flows back to ViewModel
    ↓
ViewModel emits new UI state
    ↓
Fragment renders via ViewBinding
```

---

## 5. Getting Started

### Prerequisites

- Android Studio (latest stable)
- Android SDK 35
- Java 17 (JDK 17)
- A running BASARAT backend instance (the app targets `http://193.123.84.223:8000/` by default)

### Build

```bash
# Clone
git clone <repository-url>
cd BasaratTradeInvest

# Debug build
./gradlew assembleDebug

# Run unit tests (JVM only, no emulator required)
./gradlew testDebugUnitTest
```

### Environment

Create `app/local.properties` (gitignored) pointing to your Android SDK:

```properties
sdk.dir=C:\\Users\\<your-username>\\AppData\\Local\\Android\\Sdk
```

---

## 6. Project Structure

```
app/src/main/java/com/fyp/basarattradeinvest/
├── BasaratApplication.kt        Application entry point
├── MainActivity.kt              Single Activity host
├── core/                        Cross-cutting infrastructure (17 files)
│   ├── network/                 Auth interceptor, token refresh, error parser
│   ├── session/                 Session manager, encrypted token storage
│   ├── notifications/           FCM service, WorkManager registration worker
│   └── ui/                      Custom chart views
├── data/                        Backend integration (109 files)
│   ├── remote/                  NetworkClient, Retrofit API interfaces, DTOs
│   ├── repository/              Repository implementations (21)
│   └── mapper/                  DTO → Domain model mappers (12)
├── domain/                      Pure business logic (113 files)
│   ├── model/                   Domain models (42, zero Android imports)
│   ├── repository/              Repository interfaces (20)
│   └── usecase/                 Use cases (51, one per operation)
└── feature/                     20 UI packages (170 files)
    ├── stock/                   Stock detail, analysis, chart, search
    ├── community/               Posts, comments, moderation hub
    ├── portfolio/               Holdings, transactions, risk analytics
    ├── recommendation/          AI picks, settings, smart selection
    ├── sentiment/               News & market sentiment
    ├── etf/ ipo/ alerts/ news/ shariah/ risk/ dashboard/ auth/ onboarding/
```

---

## 7. API & Backend

The app consumes **121 REST endpoints** across 21 Retrofit service interfaces:

| Service | Endpoints | Purpose |
|---|---|---|
| Community | 20 | Posts, comments, moderation |
| Market | 13 | Indices, sectors, movers, constituents |
| Auth | 11 | Login, signup, password reset, refresh |
| Portfolio | 12 | Holdings, transactions |
| News | 8 | Financial news & events |
| Assistant | 8 | AI chat assistant |
| Stocks | 5 | Search, overview, price history, technical indicators, fundamentals |
| Users | 5 | Profile, preferences |
| Recommendations | 5 | AI picks, engine weights |
| ETF / IPO / Risk / Sentiment / Shariah / Forecast | ~4 each | Feature-specific data |

Real-time market data arrives via WebSocket (`/api/v1/ws/market`).

---

## 8. Testing

All unit tests run on the **plain JVM** (no emulator required) because the `domain/` layer has no Android dependencies.

```bash
./gradlew testDebugUnitTest
```

Test coverage includes DTO→domain mapping, ViewModel logic, use-case validation, and repository behavior with fake repositories.

---

## 9. Security Notes

- Access tokens and refresh tokens are encrypted at rest using **AES-256-GCM** with keys stored in the **Android Keystore** hardware-backed storage.
- All network requests carry `Authorization: Bearer <token>`; auth endpoints are explicitly excluded.
- Token refresh on 401 is thread-safe with a `synchronized` lock and retry-count protection to prevent refresh stampedes.
- No credentials are logged — HTTP interceptors redact `Authorization`, `Cookie`, and `Set-Cookie` headers.

---

## 10. Financial Disclaimer

BASARAT is a **decision-support tool**, not financial advice. All predictions, signals, and analytics are probabilistic outputs generated by machine-learning models and quantitative algorithms. They do not constitute guaranteed outcomes or registered financial advice. Users should consult a qualified financial advisor before making investment decisions.

---

## 11. License

[Specify your license here — e.g., MIT, Apache-2.0, or proprietary]

---

*Built for the Pakistan Stock Exchange (PSX) market. Data sourced from backend ML services; not affiliated with PSX or any regulator.*