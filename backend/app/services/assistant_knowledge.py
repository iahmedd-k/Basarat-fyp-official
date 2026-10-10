"""
Comprehensive Basarat Feature & Methodology Knowledge Base.

Provides structured, in-memory & Redis-cached architectural knowledge
for the AI Assistant to answer detailed user inquiries regarding every
app feature, mathematical model, and methodology with zero latency.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from app.core.redis import cache_get, cache_set

log = logging.getLogger(__name__)

FEATURE_KNOWLEDGE_CACHE_KEY = "assistant:knowledge:features:v1"
FEATURE_KNOWLEDGE_TTL = 86400  # 24 hours

# In-memory L1 cache for sub-millisecond retrieval
_L1_KNOWLEDGE: Optional[Dict[str, Any]] = None


BASARAT_FEATURE_KNOWLEDGE: Dict[str, Any] = {
    "ai_forecast": {
        "title": "Dual-Engine AI Price Forecasting (GRU + XGBoost)",
        "architecture": "Ensemble Machine Learning combining Deep Learning (Gated Recurrent Units - GRU) for sequential price patterns and Gradient Boosted Trees (XGBoost) for tabular technical and macroeconomic features.",
        "horizons": {
            "1D": "1 Trading Day (next session direction)",
            "1W": "1 Week (5 trading days, primary swing horizon)",
            "2W": "2 Weeks (10 trading days, intermediate swing horizon)",
            "1M": "1 Month (22 trading days, monthly trend horizon)"
        },
        "outputs": "Probabilities across 3 classes: Bullish, Bearish, Sideways. Top class probability represents overall confidence.",
        "target_stop_loss_methodology": "Computed using Average True Range (ATR 14). For Bullish: Target = Current Price + (Multiplier * ATR), Stop Loss = Current Price - (1.0 * ATR). For Bearish: Target = Current Price - (Multiplier * ATR), Stop Loss = Current Price + (1.0 * ATR). Neutral forecasts use an ATR volatility envelope.",
        "feature_inputs": "Historical OHLCV, RSI 14, MACD (12,26,9), Bollinger Bands, ADX 14, Volume Z-Scores, Sector Momentum, and Macroeconomic indicators.",
        "execution_schedule": "Pre-market batch update at 05:30 PKT, daily outcome evaluation and accuracy verification at 18:00 PKT."
    },
    "recommendations": {
        "title": "Smart Multi-Factor Stock Recommendations",
        "methodology": "Ranks stocks based on ensemble forecast confidence, Risk-Reward Ratio (Target Gain vs Stop Loss Risk), technical momentum confirmation (RSI < 70, positive MACD histogram), and trading volume liquidity.",
        "ratings": {
            "Strong Buy": "Bullish probability >= 58% with high confidence and favorable risk-reward ratio >= 1.5",
            "Buy": "Bullish probability > 50% with positive technical alignment",
            "Neutral / Hold": "Sideways dominant or conflicting technical signals",
            "Sell": "Bearish probability > 50%",
            "Strong Sell": "Bearish probability >= 58% with breakdown momentum"
        }
    },
    "shariah_screener": {
        "title": "Official PSX KMI-30 Shariah Screening & Halal Investing",
        "methodology": "Applies the official SECP / PSX KMI-30 Islamic finance criteria across all listed companies to verify Shariah compliance.",
        "screening_rules": {
            "business_activity": "Excludes conventional interest-based banking, conventional insurance/takaful underwriting, alcohol, tobacco, gambling, weapons, and non-halal food.",
            "debt_ratio": "Total interest-bearing debt / Total assets MUST be LESS than 37%.",
            "interest_income_ratio": "Interest-bearing income & non-compliant revenue / Gross revenue MUST be LESS than 5%.",
            "illiquid_assets_ratio": "Illiquid assets (Fixed Assets + Inventory) / Total assets MUST be GREATER than 25%.",
            "non_compliant_investments": "Non-compliant & interest-bearing investments / Total assets MUST be LESS than 33%.",
            "net_liquid_assets": "Net liquid assets per share must be less than the market share price for equity trading validity."
        },
        "purification_formula": "Dividend Purification Amount = Dividend Income * (Non-Compliant Income / Total Revenue). Non-compliant income portion must be donated to charity without claiming tax benefit or reward."
    },
    "risk_engine": {
        "title": "Institutional Portfolio Risk & Stress Testing Engine",
        "metrics": {
            "value_at_risk_var": "Calculates maximum potential loss at 95% and 99% confidence levels over 1-day, 10-day, and 1-month horizons using both Historical Simulation and Parametric Variance-Covariance models.",
            "conditional_var_cvar": "Expected Shortfall (CVaR) measures the average loss in the extreme tail events exceeding the VaR threshold.",
            "monte_carlo_simulation": "Runs 1,000+ stochastic price trajectories using Geometric Brownian Motion (GBM) with drift and volatility to forecast portfolio value distribution over 30 to 365 days.",
            "scenario_stress_testing": "Simulates historical shocks on the portfolio: 2008 Global Financial Crisis, 2020 COVID Market Crash, 500 bps Policy Rate Hike, 30% Inflation Surge.",
            "sharpe_ratio": "(Portfolio Return - Risk Free Rate) / Portfolio Volatility. Uses 6-Month Pakistan Treasury Bill (T-Bill) yield as benchmark risk-free rate."
        }
    },
    "technical_analysis": {
        "title": "Technical Indicators & Charting Suite",
        "indicators": {
            "rsi": "Relative Strength Index (14-period Wilder smoothing). Overbought > 70, Oversold < 30.",
            "macd": "Moving Average Convergence Divergence (12 EMA, 26 EMA, 9 Signal EMA). Signal line crossovers and histogram divergence.",
            "bollinger_bands": "20 SMA baseline with Upper and Lower bands at +/- 2 Standard Deviations.",
            "adx": "Average Directional Index (14-period). Measures trend strength regardless of direction (> 25 indicates strong trend).",
            "moving_averages": "Simple Moving Averages for short (SMA 20), medium (SMA 50), and long-term (SMA 200) trend confirmation (Golden Cross / Death Cross)."
        }
    },
    "fundamental_analysis": {
        "title": "Fundamental Valuation & Financial Statements",
        "metrics": "Price to Earnings (P/E), Earnings Per Share (EPS), Dividend Yield %, Market Capitalization, Return on Equity (ROE), Debt-to-Equity Ratio, Book Value Per Share, and historical corporate announcements."
    },
    "portfolio_tracker": {
        "title": "Live Portfolio Management & P&L Tracker",
        "capabilities": "Tracks multiple asset holdings, real-time unrealized and realized P&L, weighted sector allocation breakdown, historical buy/sell trade execution logs, and live performance comparison against the KSE-100 benchmark."
    },
    "ipos_primary_market": {
        "title": "PSX IPO Tracker & Primary Market Hub",
        "features": "Live calendar of upcoming and listed PSX Initial Public Offerings. Tracks Book Building dates, floor prices, Dutch auction strike price discovery, public subscription windows, first-day listing gains, total listing return %, and provides direct downloads for SECP-approved prospectuses."
    },
    "etfs": {
        "title": "PSX Exchange Traded Funds (ETFs) Hub",
        "features": "Tracks active PSX ETFs (e.g. MIIETF, MZNPETF, NITGETF, UBLPETF, JSGBETF). Provides Net Asset Value (NAV), tracking error against underlying index benchmarks, total expense ratios (TER), fund manager details, and constituent basket weight breakdowns."
    },
    "news_sentiment": {
        "title": "Real-Time News & FinBERT NLP Sentiment Analysis",
        "pipeline": "Scrapes and aggregates financial news from top Pakistani business dailies (Business Recorder, Dawn, Profit, The News). An automated NLP pipeline evaluates sentiment polarity (Bullish, Bearish, Neutral) on a -1.0 to +1.0 scale and links catalysts to impacted stock symbols."
    },
    "community": {
        "title": "Investor Social Community Hub",
        "features": "Real-time investor discussion feeds, stock-specific commentary threads, comment replies, upvoting, verified investor badges, and community market sentiment polls."
    },
    "subscriptions": {
        "title": "Subscription Plans & Access Tiers",
        "tiers": {
            "free": "Real-time market quotes, basic technical charts, 1-horizon standard forecasts, and community access.",
            "pro": "Unlimited AI Assistant queries, full 4-horizon dual-engine forecasts (1D/1W/2W/1M), complete institutional risk suite (VaR, Monte Carlo, Stress Tests), advanced Shariah screener with purification calculations, and real-time custom price/volume alerts."
        }
    }
}


class AssistantKnowledgeService:
    """Provides ultra-fast access to Basarat app feature knowledge with Redis and L1 caching."""

    @classmethod
    async def get_feature_knowledge(cls) -> Dict[str, Any]:
        """Return full feature knowledge dictionary with sub-millisecond latency."""
        global _L1_KNOWLEDGE
        if _L1_KNOWLEDGE is not None:
            return _L1_KNOWLEDGE

        cached = await cache_get(FEATURE_KNOWLEDGE_CACHE_KEY)
        if isinstance(cached, dict) and cached:
            _L1_KNOWLEDGE = cached
            return cached

        # Populate Redis and memory
        _L1_KNOWLEDGE = BASARAT_FEATURE_KNOWLEDGE
        try:
            await cache_set(FEATURE_KNOWLEDGE_CACHE_KEY, BASARAT_FEATURE_KNOWLEDGE, ttl_seconds=FEATURE_KNOWLEDGE_TTL)
        except Exception as exc:
            log.warning("Could not cache feature knowledge in Redis: %s", exc)

        return _L1_KNOWLEDGE

    @classmethod
    def get_feature_summary_text(cls) -> str:
        """Format the complete feature knowledge into a clean, authoritative reference string."""
        sections = []
        for key, item in BASARAT_FEATURE_KNOWLEDGE.items():
            title = item.get("title", key.upper())
            lines = [f"### Feature: {title}"]
            for field, val in item.items():
                if field == "title":
                    continue
                if isinstance(val, dict):
                    lines.append(f"- {field}:")
                    for sub_k, sub_v in val.items():
                        lines.append(f"  * {sub_k}: {sub_v}")
                elif isinstance(val, list):
                    lines.append(f"- {field}: " + ", ".join(str(x) for x in val))
                else:
                    lines.append(f"- {field}: {val}")
            sections.append("\n".join(lines))
        return "\n\n".join(sections)
