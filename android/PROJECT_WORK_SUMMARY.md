# BASARAT (بصيرة) — Development Progress & Completed Work Summary
### Trade Recommendation and Assistance System for Pakistan Stock Exchange (PSX)
**Document Version:** 1.0  
**Target Platform:** Native Android (Kotlin + XML + Material Components)  
**Architecture:** Clean Architecture + MVVM + Repository Pattern  
**Date:** September 2026  

---

## 1. Executive Summary

**BASARAT** is a mobile-first financial decision-support system designed specifically for investors and traders on the **Pakistan Stock Exchange (PSX)**. The platform bridges the gap between complex quantitative market data and actionable trading decisions by synthesizing:
* Real-time and historical technical stock analysis.
* Fundamental valuation and financial solvency ratios.
* Islamic Shariah compliance screening (KMI-30 alignment & dividend purification).
* Deep learning stock price forecasts (GRU models) and NLP sentiment analysis (FinBERT).
* Community intelligence and trade setups.

The Android mobile client functions as the **pure presentation and interaction layer**, consuming pre-calculated quantitative feeds and backend ML APIs while enforcing immutable, unidirectional UI state management.

---

## 2. Technology Stack & Architectural Standards

| Dimension | Technology / Standard | Purpose |
| :--- | :--- | :--- |
| **Language** | Kotlin 1.9+ | Modern, expressive, null-safe development |
| **UI Framework** | Native Android XML Layouts + Material 3 | Strict adherence to project contract (No Compose) |
| **Architecture** | Clean Architecture + MVVM | Strict separation of Presentation, Domain, and Data |
| **State Management** | Kotlin Coroutines + `StateFlow` | Immutable, reactive unidirectional data flow (`UiState`) |
| **View Binding** | Android Jetpack ViewBinding | Type-safe, null-safe view references |
| **Navigation** | Android Jetpack Navigation Component | Single-Activity architecture (`MainActivity` + `NavHostFragment`) |
| **Charting** | MPAndroidChart | High-performance interactive candlestick & volume charting |
| **Networking** | Retrofit 2 + OkHttp 3 + Gson | REST API consumption & JSON serialization |
| **Build System** | Gradle Kotlin DSL (`build.gradle.kts`) | Compile SDK 35, Min SDK 24, Target SDK 35, Java 17 |

---

## 3. UI State Contract

Every network-backed or dynamic screen follows a strict, finite 4-state sealed interface to guarantee that conflicting states (e.g., loading while showing errors) are mathematically impossible:

```kotlin
sealed interface UiState<out T> {
    data object Loading : UiState<Nothing>
    data class Success<T>(val data: T) : UiState<T>
    data object Empty : UiState<Nothing>
    data class Error(val message: String) : UiState<Nothing>
}
```

---

## 4. Comprehensive Inventory of Completed Work

### 4.1. Core Foundation & Design System
* **Color System**:
  * `Primary Background`: Pure White (`#FFFFFF`) & Surface Canvas (`#F7F9F8`).
  * `Text Hierarchy`: Primary Text (`#111827`), Secondary Text (`#667085`), Tertiary (`#98A2B3`).
  * `Brand Accents`: BASARAT Green (`#00B894`), Dark Green (`#087F5B`).
  * `Financial Semantics`: Positive Gain / Bullish (`#18B981`), Loss / Bearish (`#EF4444`).
  * `Intelligence Accents`: Shariah Teal (`#14A89B`), AI Blue (`#4F7CFF`), Gold Accent (`#D4A84F`).
* **Spacing & Styling**:
  * Strict 8dp grid system (`4dp`, `8dp`, `12dp`, `16dp`, `24dp`, `32dp`).
  * Reusable drawables created for positive, negative, neutral, strong-buy, and Shariah badges, card strokes, and segmented switch containers.

---

### 4.2. Onboarding & Authentication Module
* **Splash Screen (`SplashFragment`)**: Animated brand bootstrap directing new users to onboarding or authenticated users to the home dashboard.
* **Onboarding Flow (`OnboardingFragment`, `OnboardingAdapter`)**: 3-step value proposition carousel introducing PSX market intelligence, AI forecasting, and Shariah screening.
* **Authentication (`LoginFragment`, `SignUpFragment`)**:
  * Clean Material text input fields with toggleable password visibility.
  * Form validation, social sign-in buttons (Google & Apple), and navigation actions.

---

### 4.3. Market Dashboard Module
* **Screen (`MarketDashboardFragment`, `MarketDashboardViewModel`)**:
  * Real-time KSE-100, KSE-30, and KMI-30 market indices header.
  * Market status indicators (Open/Closed, live updates).
  * Top Gainers, Top Losers, and Most Active stocks lists.
  * Sector performance breakdown with visual percentage bars.
  * Navigation shortcuts to Shariah Screening and Stock Details.

---

### 4.4. Shariah Compliance Screening Module
* **Screen (`ShariahScreeningFragment`, `ShariahScreeningViewModel`)**:
  * Dedicated to PSX Shariah-compliant equities.
  * Filter pills: `All Stocks`, `KMI-30`, and `KMI All Share`.
  * Multi-column tabular view: Symbol, Current Price, Daily % Change, and Dividend Purification %.
  * Real-time search query filtering by PSX symbol or company name.

---

### 4.5. Stock Details Screen
* **Screen (`StockDetailFragment`, `StockDetailViewModel`)**:
  * **Stock Header**: Symbol, company name, live PKR price, change badge, 52-week range, open/high/low/volume stats.
  * **Interactive Candlestick Chart**: Built using `MPAndroidChart` with timeframe selection pills (`1D`, `Daily`, `Weekly`, `1M`).
  * **Volume Chart**: Synchronized volume bars with color-coded buying/selling pressure.
  * **Integrated Section Tabs**:
    * **Quotes**: Sub-pills for `By Price` (detailed stats), `Trades` (recent transaction ticker), `Detailed Quote`, and `Liquidity`.
    * **Analysis**: Directly navigates to the dedicated Stock Analysis screen.
    * **News**: Company-specific financial announcements.
    * **Profile**: Company overview, sector classification, and board profile.

---

### 4.6. Stock Technical & Fundamental Analysis Module
* **Screen (`StockAnalysisFragment`, `StockAnalysisViewModel`)**:
  * Designed as a dedicated quantitative analysis terminal (not a duplicate detail screen).
  * **Header**: Compact ticker identity (`LUCK`, `Lucky Cement Limited`, `PKR 412.80 +3.10%`).
  * **Segmented Switcher**: Smooth toggle between **Technical Analysis** and **Fundamentals**.
  * **Technical Analysis Section**:
    * **Technical Summary Meter**: Aggregated score counter (`15 Buy`, `4 Neutral`, `1 Sell`), prominent `STRONG BUY` badge, and tri-color visual gauge bar.
    * **Oscillators Table**: RSI (14) with status, MACD (12,26,9) with bullish crossover, ADX (14) trend strength, Stochastic %K, and Bollinger Bands %B.
    * **Moving Averages Card**: SMA 20, SMA 50, SMA 200, and EMA 20 with price comparison and signal badges.
    * **Pivot Points (Classic)**: Complete support and resistance grid ($R3, R2, R1$, Central Pivot $P$, $S1, S2, S3$).
  * **Fundamentals Section**:
    * **Valuation Multiples**: P/E Ratio (TTM), Forward P/E, Price-to-Book (P/B), EV/EBITDA, and PEG Ratio.
    * **Profitability & Returns**: EPS (TTM), Return on Equity (ROE), Return on Assets (ROA), Dividend Yield, Net Profit Margin.
    * **Financial Health & Solvency**: Debt-to-Equity (D/E), Current Ratio, Quick Ratio, Interest Coverage.
    * **Annual Financial Performance**: TTM Revenue, Net Income, and Free Cash Flow.

---

## 5. End-to-End Navigation Flow

```text
[Splash] ──> [Onboarding] ──> [Login / Register]
                                    │
                                    ▼
                          [Market Dashboard]
                           │              │
        ┌──────────────────┘              └──────────────────┐
        ▼                                                    ▼
[Shariah Screening]                                  [Stock Details]
        │                                             (Chart, Quotes)
        └─────────────────> [Stock Details]                  │
                                   │                         ▼
                                   └────────────> [Stock Analysis]
                                                  (Technical / Fundamentals)
```

---

## 6. Verification and Code Quality Status
* **Compilation**: Zero compilation errors across Kotlin, Java, and XML resources.
* **View Binding**: All fragments clear their `_binding` in `onDestroyView()` to prevent memory leaks.
* **Coroutines**: All asynchronous state updates use `repeatOnLifecycle(Lifecycle.State.STARTED)` for safe UI rendering.
* **Architecture Compliance**: No business logic or direct indicator calculations reside in UI components; all data flows through domain models and repository interfaces.

---

*This document can be copied directly into Microsoft Word or Google Docs for project reviews, FYP documentation submissions, or client presentations.*
