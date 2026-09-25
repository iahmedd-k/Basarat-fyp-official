"""Safety and guardrails for the Stock AI Assistant."""

import logging
import re
from typing import Literal, Optional, Tuple

log = logging.getLogger(__name__)


class SafetyError(Exception):
    """Safety violation error."""

    def __init__(self, message: str, violation_type: str):
        self.violation_type = violation_type
        super().__init__(message)


# ──────────────────────────────────────────────────────────────────────
# Intent Classification
# ──────────────────────────────────────────────────────────────────────

IntentType = Literal[
    "stock_information",
    "market_information",
    "portfolio_information",
    "risk_profile",
    "forecast_explanation",
    "financial_education",
    "application_help",
    "portfolio_analysis",
    "stock_analysis",
    "personalized_investment_advice",
    "off_topic",
    "unsafe",
]


# Keywords for intent classification
INTENT_KEYWORDS = {
    "stock_information": [
        "stock", "share", "price", "quote", "chart", "technical", "rsi", "macd",
        "bollinger", "moving average", "sma", "ema", "volume", "ohlcv",
        "fundamental", "earnings", "pe ratio", "dividend", "market cap",
        "overview", "company", "sector", "symbol"
    ],
    "market_information": [
        "market", "kse", "index", "kse100", "kse30", "kmi30", "gainers", "losers",
        "volume spikes", "market status", "trading hours", "sentiment overview"
    ],
    "portfolio_information": [
        "portfolio", "holding", "holdings", "my stocks", "my portfolio",
        "allocation", "diversification", "concentration", "exposure",
        "pnl", "profit", "loss", "performance", "returns", "weight"
    ],
    "risk_profile": [
        "risk profile", "risk tolerance", "conservative", "moderate", "aggressive",
        "investment horizon", "sector preference", "risk appetite"
    ],
    "forecast_explanation": [
        "forecast", "prediction", "predict", "model", "gru", "xgb", "ensemble",
        "bullish", "bearish", "sideways", "confidence", "probability",
        "direction", "target price", "stop loss", "forecast history"
    ],
    "financial_education": [
        "what is", "define", "explain", "how does", "what does", "meaning of",
        "rsi", "macd", "pe ratio", "volatility", "diversification", "var",
        "cvar", "monte carlo", "stress test", "sharpe", "drawdown"
    ],
    "application_help": [
        "how to", "how do i", "feature", "app", "application", "setting",
        "notification", "alert", "community", "shariah", "portfolio"
    ],
    "portfolio_analysis": [
        "analyze my portfolio", "portfolio analysis", "evaluate portfolio",
        "portfolio review", "sector concentration", "diversification"
    ],
    "stock_analysis": [
        "analyze", "evaluate", "assess", "review", "deep dive", "technical analysis",
        "fundamental analysis", "should i buy", "should i sell", "good investment",
        "good stock", "bad stock", "worth buying", "worth selling"
    ],
    "personalized_investment_advice": [
        "should i buy", "should i sell", "should i hold", "how much to buy",
        "how much to sell", "how much to invest", "how much should i invest",
        "position size", "allocation", "entry price", "exit price",
        "best stock for me", "recommend me", "what should i do",
        "tell me what to buy", "tell me what to sell", "what to buy",
        "what to sell", "guaranteed", "sure thing", "best bet",
        "how much to allocate", "what to allocate"
    ],
    "off_topic": [
        "joke", "game", "recipe", "weather", "movie", "music", "sports",
        "politics", "religion", "programming", "code", "python", "javascript",
        "quantum", "world war", "history", "biology", "chemistry", "physics",
        "essay", "story", "poem", "creative writing"
    ],
    "unsafe": [
        "system prompt", "ignore previous", "ignore instructions", "reveal",
        "secret", "api key", "password", "credential", "token", "database",
        "internal", "configuration", "admin", "root", "sudo", "hack",
        "exploit", "bypass", "override", "jailbreak"
    ],
}


def classify_intent(message: str) -> str:
    """
    Classify user message intent using keyword matching and rules.

    Returns one of the IntentType values.
    """
    message_lower = message.lower().strip()

    # Check for unsafe / prompt injection first (highest priority)
    if check_prompt_injection(message):
        return "unsafe"
    for keyword in INTENT_KEYWORDS["unsafe"]:
        if keyword in message_lower:
            return "unsafe"

    # Check for off-topic (unless specifically discussing finance concepts)
    for keyword in INTENT_KEYWORDS["off_topic"]:
        if keyword in message_lower:
            return "off_topic"

    # Check for personalized investment advice (critical safety)
    for keyword in INTENT_KEYWORDS["personalized_investment_advice"]:
        if keyword in message_lower:
            return "personalized_investment_advice"

    # Portfolio analysis vs portfolio info
    if re.search(r"\banalyze\s+(?:my\s+)?portfolio\b|\bevaluate\s+(?:my\s+)?portfolio\b", message_lower):
        return "portfolio_analysis"

    # Stock analysis
    if re.search(r"\banalyze\s+[a-z0-9]+\b|\bevaluate\s+[a-z0-9]+\b|\bassess\s+[a-z0-9]+\b|\bthoughts\s+on\b|\bview\s+on\b|\boutlook\b", message_lower):
        return "stock_analysis"

    # App navigation/setup questions take precedence over the word
    # "portfolio" (for example, "How do I create a portfolio?").
    if re.search(r"\bhow\s+do\s+i\b|\bhow\s+to\b|\bfeatures?\b|\bhelp\b|\bsettings?\b|\balerts?\b", message_lower):
        return "application_help"

    # Forecast explanation
    if "forecast" in message_lower or "prediction" in message_lower or "predict" in message_lower or "target" in message_lower:
        return "forecast_explanation"

    # Risk profile
    if re.search(r"\brisk\s+profile\b|\brisk\s+tolerance\b|\bhorizon\b|\bconservative\b|\baggressive\b", message_lower):
        return "risk_profile"

    # Portfolio information
    if re.search(
        r"\bholdings?\b|\bmy\s+(?:portfolio|stocks?|positions?|investments?)\b|"
        r"\bportfolio\s+(?:value|pnl|performance|allocation|holdings?)\b|"
        r"\b(?:pnl|profit|loss|returns|diversification|concentration|exposure)\b",
        message_lower,
    ) or (
        re.search(r"\bportfolio\b", message_lower)
        and not re.search(r"\b(?:what is|define|meaning of)\s+(?:a |the )?portfolio\b", message_lower)
    ):
        return "portfolio_information"

    # Market information
    if re.search(r"\bmarket\b|\bgainers?\b|\blosers?\b|\bindices\b|\bkse\b|\bkse100\b|\bpsx\b|\bturnover\b|\bvolume\b|\bnews\b|\bannouncements?\b", message_lower):
        return "market_information"

    concept_abbreviations = {"RSI", "MACD", "SMA", "EMA", "ATR", "VAR", "CVAR", "EPS", "ROI", "PPE"}
    explicit_tickers = re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,5}(?![A-Za-z0-9])", message)
    if any(ticker not in concept_abbreviations for ticker in explicit_tickers):
        return "stock_information"

    # General financial education should not be misclassified merely because
    # the concept (RSI, P/E, dividend) is also a supported stock metric.
    if re.search(r"\bwhat\s+is\b|\bexplain\b|\bdefine\b|\bmeaning\s+of\b|\bhow\s+does\b|\bconcept\b|\bdividend\b|\bpe\s+ratio\b|\bvaluation\b|\bshariah\b", message_lower):
        return "financial_education"

    # Route live company/metric lookups after education intents.
    for kw in INTENT_KEYWORDS["stock_information"]:
        if kw in message_lower:
            return "stock_information"

    # If message contains uppercase candidate ticker or financial query terms
    if any(term in message_lower for term in ["about", "detail", "performance", "shares", "company", "price", "rate", "status"]):
        return "stock_information"

    # If there is a plausible stock symbol (2-5 uppercase chars)
    words = [re.sub(r'[^A-Za-z0-9]', '', w) for w in message.split()]
    if any(w.isupper() and 2 <= len(w) <= 6 for w in words):
        return "stock_information"

    return "off_topic"


# ──────────────────────────────────────────────────────────────────────
# Output Safety Check
# ──────────────────────────────────────────────────────────────────────

# Patterns that indicate personalized investment advice
PROHIBITED_PATTERNS = [
    (r"\byou should buy\b", "direct_buy_advice"),
    (r"\byou should (?:purchase|invest in)\b", "direct_buy_advice"),
    (r"\byou should sell\b", "direct_sell_advice"),
    (r"\byou should (?:liquidate|dispose of)\b", "direct_sell_advice"),
    (r"\byou should avoid\b", "direct_avoid_instruction"),
    (r"\byou should hold\b", "direct_hold_advice"),
    (r"\bi recommend (?:that you )?(?:buy|purchase|sell|hold|avoid|invest in|buying|purchasing|selling|holding)\b", "personalized_recommendation"),
    (r"\bi suggest (?:that you )?(?:buy|purchase|sell|hold|avoid|invest in)\b", "personalized_recommendation"),
    (r"\bmy recommendation is to (?:buy|purchase|sell|hold|avoid|invest in)\b", "personalized_recommendation"),
    (r"\b(?:best|ideal|perfect) (?:stock|investment|option) for you\b", "personalized_recommendation"),
    (r"(?:^|[\n.!?]\s*)(?:[-*]\s*)?(?:buy|sell|hold|purchase|avoid)\s+(?:shares of\s+)?[A-Z]{2,5}\b", "direct_trade_instruction"),
    (r"\bbuy this stock\b", "direct_buy_instruction"),
    (r"\bsell this stock\b", "direct_sell_instruction"),
    (r"\ballocate\s+\d+%?\b", "allocation_instruction"),
    (r"\binvest\s+\$\d+", "amount_instruction"),
    (r"\binvest\s+\d+%?", "percentage_instruction"),
    (r"\bguaranteed return\b", "guaranteed_return"),
    (r"\bguaranteed profit\b", "guaranteed_profit"),
    (r"\byou need to buy\b", "necessity_buy"),
    (r"\byou need to sell\b", "necessity_sell"),
    (r"\bbest stock for you\b", "personalized_recommendation"),
    (r"\bbest stock for me\b", "personalized_recommendation"),
    (r"\btell me what to buy\b", "direct_buy_request"),
    (r"\btell me what to sell\b", "direct_sell_request"),
    (r"\bexactly what to buy\b", "direct_buy_instruction"),
    (r"\bexactly what to sell\b", "direct_sell_instruction"),
    (r"\bput \d+%? (?:of|in) (?:your|the) portfolio\b", "allocation_instruction"),
    (r"\bentry price.*\$\d+", "entry_price_instruction"),
    (r"\bexit price.*\$\d+", "exit_price_instruction"),
    (r"\b(?:buy|sell)\s+(?:[a-zA-Z0-9_-]+\s+)?(?:tomorrow|today|now)\b", "timing_instruction"),
    (r"\b(?:tomorrow|today|now)\s+(?:buy|sell)\b", "timing_instruction"),
]

# Compile patterns for performance
PROHIBITED_REGEX = [(re.compile(pattern, re.IGNORECASE), vtype) for pattern, vtype in PROHIBITED_PATTERNS]


def check_output_safety(response: str) -> tuple[bool, Optional[str]]:
    """
    Check if the assistant's response contains prohibited content.

    Returns:
        (is_safe, violation_type)
    """
    for pattern, vtype in PROHIBITED_REGEX:
        if pattern.search(response):
            log.warning(f"Output safety violation: {vtype} - matched: {pattern.pattern}")
            return False, vtype
    return True, None


def sanitize_response(response: str) -> str:
    """
    Attempt to sanitize a response by removing or replacing prohibited patterns.

    This is a best-effort sanitization. If the response is heavily violating,
    it's better to regenerate.
    """
    sanitized = response
    for pattern, vtype in PROHIBITED_REGEX:
        if pattern.search(sanitized):
            # Replace with a generic safe alternative
            if "buy" in vtype:
                sanitized = pattern.sub("consider analyzing whether to buy", sanitized)
            elif "sell" in vtype:
                sanitized = pattern.sub("consider analyzing whether to sell", sanitized)
            elif "hold" in vtype:
                sanitized = pattern.sub("consider your holding strategy", sanitized)
            elif "allocate" in vtype or "allocation" in vtype or "invest" in vtype or "percentage" in vtype or "amount" in vtype:
                sanitized = pattern.sub("consider your allocation strategy", sanitized)
            elif "guaranteed" in vtype:
                sanitized = pattern.sub("potential", sanitized)
            elif "need to" in vtype:
                sanitized = pattern.sub("could consider", sanitized)
            elif "best stock for" in vtype:
                sanitized = pattern.sub("stocks matching your criteria", sanitized)
            elif "tell me what" in vtype:
                sanitized = pattern.sub("I can help you analyze", sanitized)
            elif "entry price" in vtype or "exit price" in vtype:
                sanitized = pattern.sub("price levels to watch", sanitized)
            elif "timing" in vtype or "tomorrow" in vtype:
                sanitized = pattern.sub("in the near term", sanitized)
            else:
                sanitized = pattern.sub("[analysis redirected]", sanitized)

    return sanitized


def enforce_output_safety(response: str) -> tuple[str, bool, Optional[str]]:
    """Return one complete response that passes the output policy.

    Callers must emit this checked response, never the unchecked model text.
    """
    is_safe, violation_type = check_output_safety(response)
    if is_safe:
        return response, False, None

    # Avoid fragile in-place edits that can change the meaning of a financial
    # sentence. Replace the whole answer with a vetted, topic-specific redirect.
    return get_safety_response(violation_type or "default"), True, violation_type


def check_prompt_injection(message: str) -> bool:
    """
    Check for prompt injection attempts.

    Returns True if injection detected.
    """
    injection_patterns = [
        r"ignore (?:all )?previous instructions",
        r"ignore (?:all )?instructions",
        r"reveal (?:your )?system prompt",
        r"reveal (?:your )?instructions",
        r"show (?:me )?(?:your )?system prompt",
        r"what (?:is|are) (?:your )?system prompt",
        r"forget (?:all )?(?:previous|above)",
        r"you are now",
        r"act as",
        r"pretend to be",
        r"roleplay as",
        r"developer mode",
        r"admin mode",
        r"god mode",
        r"unrestricted",
        r"no (?:rules|restrictions|limits)",
        r"bypass",
        r"override",
        r"jailbreak",
    ]

    message_lower = message.lower()
    for pattern in injection_patterns:
        if re.search(pattern, message_lower):
            log.warning(f"Prompt injection detected: {pattern}")
            return True
    return False


def get_safety_response(violation_type: str) -> str:
    """Get a safe, educational response for a safety violation."""
    responses = {
        "direct_buy_advice": (
            "I can't provide personalized buy recommendations, but I can help you analyze "
            "the stock's fundamentals, technical indicators, forecasts, and how it might fit "
            "your portfolio and risk profile."
        ),
        "direct_sell_advice": (
            "I can't provide personalized sell recommendations, but I can help you evaluate "
            "your holding's performance, forecast outlook, and how it aligns with your "
            "investment goals and risk tolerance."
        ),
        "direct_hold_advice": (
            "I can't tell you whether to hold, but I can help you review the stock's "
            "recent performance, forecast, and how it fits your investment horizon and risk profile."
        ),
        "direct_avoid_instruction": (
            "I can't tell you to avoid a specific stock, but I can help review its "
            "retrieved fundamentals, price history, forecast, and relevant risks."
        ),
        "direct_trade_instruction": (
            "I can't give a direct trade instruction. I can summarize the retrieved "
            "market, company, and risk information so you can make your own decision."
        ),
        "allocation_instruction": (
            "I can't specify portfolio allocations, but I can show you your current "
            "diversification, sector exposure, and concentration metrics so you can decide."
        ),
        "amount_instruction": (
            "I can't specify investment amounts, but I can explain position sizing concepts "
            "and risk management principles."
        ),
        "percentage_instruction": (
            "I can't specify percentage allocations, but I can show you your current "
            "portfolio weights and sector concentrations."
        ),
        "guaranteed_return": (
            "No investment has guaranteed returns. I can explain the forecast probabilities "
            "and historical volatility to help you understand the risk/return profile."
        ),
        "guaranteed_profit": (
            "There are no guaranteed profits in the stock market. I can help you understand "
            "the risk/reward profile based on forecasts, technicals, and fundamentals."
        ),
        "necessity_buy": (
            "You're not obligated to buy any stock. I can help you evaluate whether a "
            "stock aligns with your investment criteria."
        ),
        "necessity_sell": (
            "You're not obligated to sell. I can help you assess whether selling aligns "
            "with your investment thesis and risk management."
        ),
        "personalized_recommendation": (
            "I can't recommend specific stocks for you personally, but I can help you "
            "analyze stocks based on your stated risk profile, sector preferences, and "
            "investment horizon."
        ),
        "direct_buy_request": (
            "I can't make buy decisions for you, but I can walk you through the analysis "
            "framework: fundamentals, technicals, forecasts, and portfolio fit."
        ),
        "direct_sell_request": (
            "I can't make sell decisions for you, but I can help you evaluate whether "
            "selling aligns with your investment thesis."
        ),
        "entry_price_instruction": (
            "I can't set entry prices, but I can show you current levels, support/resistance, "
            "and forecast ranges."
        ),
        "exit_price_instruction": (
            "I can't set exit prices, but I can show you target/stop-loss calculations "
            "based on ATR and your risk tolerance."
        ),
        "timing_instruction": (
            "I can't time the market for you, but I can share the forecast horizon and "
            "what the model suggests for the near term."
        ),
        "default": (
            "I can't provide personalized investment decisions. I can help you analyze "
            "stocks, understand forecasts, review your portfolio, and explain financial concepts "
            "so you can make informed decisions."
        ),
    }
    return responses.get(violation_type, responses["default"])
