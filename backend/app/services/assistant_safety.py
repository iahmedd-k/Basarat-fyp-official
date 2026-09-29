"""Safety and guardrails for the Basarat Stock AI Assistant."""

from __future__ import annotations

import logging
import re
from typing import Literal, Optional

log = logging.getLogger(__name__)


class SafetyError(Exception):
    """Safety violation error."""

    def __init__(self, message: str, violation_type: str):
        self.violation_type = violation_type
        super().__init__(message)


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
    "general",
    "off_topic",
    "unsafe",
]


# ──────────────────────────────────────────────────────────────────────
# Intent Classification (soft routing for context, not hard refusals)
# ──────────────────────────────────────────────────────────────────────

def classify_intent(message: str) -> str:
    """Classify intent for context gathering. Prefer helpful defaults over off_topic."""
    message_lower = message.lower().strip()

    if check_prompt_injection(message):
        return "unsafe"

    # Clear non-finance topics only
    if re.search(
        r"\b(?:tell me a joke|write (?:a |me )?(?:poem|essay|story)|weather|"
        r"recipe|movie recommendation|play (?:a )?game|world war|"
        r"quantum (?:mechanics|physics)|biology homework|chemistry homework)\b",
        message_lower,
    ):
        return "off_topic"
    if re.search(
        r"\b(?:write|code|program)\b.{0,40}\b(?:python|javascript|java|c\+\+)\b",
        message_lower,
    ) and not re.search(r"\b(?:stock|portfolio|psx|market|finance)\b", message_lower):
        return "off_topic"

    # Personalized advice — still serve analysis context; prompt handles redirect tone
    if re.search(
        r"\bshould i (?:buy|sell|hold)\b|"
        r"\bhow much (?:should i |to )?(?:buy|sell|invest|allocate)\b|"
        r"\b(?:best|ideal) stock for (?:me|you)\b|"
        r"\brecommend (?:me |a stock|stocks)\b|"
        r"\btell me (?:exactly )?what to (?:buy|sell)\b|"
        r"\bwhat should i (?:buy|sell|do)\b|"
        r"\b(?:entry|exit) price\b|"
        r"\btarget allocation\b|"
        r"\bhow much to allocate\b",
        message_lower,
    ):
        return "personalized_investment_advice"

    if re.search(r"\banalyze\s+(?:my\s+)?portfolio\b|\bevaluate\s+(?:my\s+)?portfolio\b|\bportfolio (?:analysis|review)\b", message_lower):
        return "portfolio_analysis"

    if re.search(
        r"\banalyze\s+[a-z0-9]+\b|\bevaluate\s+[a-z0-9]+\b|\bassess\s+[a-z0-9]+\b|"
        r"\bthoughts\s+on\b|\bview\s+on\b|\boutlook\s+(?:on|for)\b|"
        r"\b(?:technical|fundamental) analysis\b",
        message_lower,
    ):
        return "stock_analysis"

    # App how-to before generic portfolio keyword
    if re.search(
        r"\bhow\s+do\s+i\b|\bhow\s+to\b|\b(?:app|application)\s+feature|"
        r"\bhelp (?:me )?(?:with|using) (?:the )?(?:app|basarat)\b|"
        r"\b(?:set(?:\s+up)?|create|enable)\s+(?:an?\s+)?(?:alert|notification|portfolio)\b",
        message_lower,
    ):
        return "application_help"

    if re.search(r"\bforecast\b|\bprediction\b|\bpredict\b|\bbullish\b|\bbearish\b|\bmodel (?:says|output)\b", message_lower):
        return "forecast_explanation"

    if re.search(r"\brisk\s+profile\b|\brisk\s+tolerance\b|\binvestment\s+horizon\b|\baggressive\b|\bconservative\b", message_lower):
        return "risk_profile"

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

    concept_abbreviations = {
        "RSI", "MACD", "SMA", "EMA", "ATR", "VAR", "CVAR", "EPS", "ROI",
        "PPE", "KSE", "KSE100", "KSE30", "KMI30", "PSX",
    }
    explicit_tickers = re.findall(r"(?<![A-Za-z0-9])[A-Z][A-Z0-9]{1,5}(?![A-Za-z0-9])", message)
    if any(ticker not in concept_abbreviations for ticker in explicit_tickers):
        return "stock_information"

    if re.search(
        r"\bmarket\b|\bgainers?\b|\blosers?\b|\bindices\b|\bkse\b|\bkse100\b|"
        r"\bkse30\b|\bkmi30\b|\bpsx\b|\bturnover\b|\bvolume\b|\bnews\b|\bannouncements?\b",
        message_lower,
    ):
        return "market_information"

    if re.search(
        r"\bwhat\s+is\b|\bexplain\b|\bdefine\b|\bmeaning\s+of\b|\bhow\s+does\b|"
        r"\bconcept\b|\bdividend\b|\bpe\s+ratio\b|\bvaluation\b|\bshariah\b|\bhalal\b",
        message_lower,
    ):
        return "financial_education"

    stock_terms = (
        "stock", "share", "price", "quote", "chart", "technical", "fundamental",
        "earnings", "sector", "symbol", "company", "shariah", "islamic", "halal",
    )
    if any(term in message_lower for term in stock_terms):
        return "stock_information"

    if any(term in message_lower for term in ("about", "detail", "performance", "shares", "rate", "status")):
        return "stock_information"

    words = [re.sub(r"[^A-Za-z0-9]", "", w) for w in message.split()]
    if any(w.isupper() and 2 <= len(w) <= 6 for w in words):
        return "stock_information"

    # Ambiguous but not clearly off-topic → keep the assistant helpful
    return "general"


# ──────────────────────────────────────────────────────────────────────
# Output Safety
# ──────────────────────────────────────────────────────────────────────

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

PROHIBITED_REGEX = [(re.compile(pattern, re.IGNORECASE), vtype) for pattern, vtype in PROHIBITED_PATTERNS]

_DISCLAIMER = (
    "\n\nThis is educational decision-support only - not personalized buy, sell, or allocate advice."
)


def check_output_safety(response: str) -> tuple[bool, Optional[str]]:
    """Return (is_safe, violation_type)."""
    for pattern, vtype in PROHIBITED_REGEX:
        if pattern.search(response):
            log.warning("Output safety violation: %s - matched: %s", vtype, pattern.pattern)
            return False, vtype
    return True, None


def sanitize_response(response: str) -> str:
    """Best-effort rewrite of prohibited phrasing while keeping useful analysis."""
    sanitized = response
    for pattern, vtype in PROHIBITED_REGEX:
        if not pattern.search(sanitized):
            continue
        if vtype in ("direct_buy_advice", "direct_buy_instruction", "necessity_buy", "direct_buy_request"):
            sanitized = pattern.sub("it may be worth analyzing a purchase of", sanitized)
        elif vtype in ("direct_sell_advice", "direct_sell_instruction", "necessity_sell", "direct_sell_request"):
            sanitized = pattern.sub("it may be worth analyzing a sale of", sanitized)
        elif "hold" in vtype:
            sanitized = pattern.sub("consider your holding strategy for", sanitized)
        elif "avoid" in vtype:
            sanitized = pattern.sub("review the risks of", sanitized)
        elif vtype == "direct_trade_instruction":
            sanitized = pattern.sub("review", sanitized)
        elif "allocate" in vtype or "allocation" in vtype or "percentage" in vtype or "amount" in vtype:
            sanitized = pattern.sub("consider allocation carefully for", sanitized)
        elif "guaranteed" in vtype:
            sanitized = pattern.sub("potential", sanitized)
        elif "personalized" in vtype:
            sanitized = pattern.sub("a stock matching your criteria could be", sanitized)
        elif "entry price" in vtype or "exit price" in vtype:
            sanitized = pattern.sub("a price level to watch is", sanitized)
        elif "timing" in vtype:
            sanitized = pattern.sub("near-term price action for", sanitized)
        else:
            sanitized = pattern.sub("review the available analysis on", sanitized)
    return sanitized


def enforce_output_safety(response: str) -> tuple[str, bool, Optional[str]]:
    """Prefer sanitizing useful answers over wiping them with a canned refusal."""
    is_safe, violation_type = check_output_safety(response)
    if is_safe:
        return response, False, None

    sanitized = sanitize_response(response)
    safe_after, still_type = check_output_safety(sanitized)
    if safe_after and len(sanitized.strip()) >= 40:
        if _DISCLAIMER.strip() not in sanitized:
            sanitized = sanitized.rstrip() + _DISCLAIMER
        return sanitized, True, violation_type

    # Last resort: short redirect that still invites a useful follow-up
    return get_safety_response(still_type or violation_type or "default"), True, violation_type


def check_prompt_injection(message: str) -> bool:
    """Detect real jailbreak / prompt-theft attempts — not normal roleplay wording."""
    message_lower = message.lower()

    strong_patterns = [
        r"ignore (?:all )?(?:previous |prior |above )?instructions",
        r"ignore (?:all )?instructions",
        r"reveal (?:your )?system prompt",
        r"reveal (?:your )?instructions",
        r"show (?:me )?(?:your )?system prompt",
        r"what (?:is|are) (?:your )?system prompt",
        r"forget (?:all )?(?:previous|above) instructions",
        r"developer mode",
        r"admin mode",
        r"god mode",
        r"jailbreak",
        r"bypass (?:the )?(?:safety|guardrail|rules|restrictions)",
        r"override (?:the )?(?:safety|guardrail|instructions|rules)",
        r"no (?:rules|restrictions|limits)(?:\s+mode)?",
        r"unrestricted (?:mode|access)",
        r"(?:api key|password|credential|database dump)",
    ]
    for pattern in strong_patterns:
        if re.search(pattern, message_lower):
            log.warning("Prompt injection detected: %s", pattern)
            return True

    # Role-switch only when paired with unrestricted / override language
    if re.search(
        r"(?:you are now|act as|pretend to be|roleplay as).{0,60}"
        r"(?:unrestricted|no rules|ignore (?:all )?instructions|jailbreak|without (?:any )?(?:rules|restrictions))",
        message_lower,
    ):
        log.warning("Prompt injection detected: role-switch + override")
        return True

    if re.search(r"you are now in (?:developer|admin|god) mode", message_lower):
        log.warning("Prompt injection detected: privileged mode")
        return True

    return False


def get_safety_response(violation_type: str) -> str:
    """Educational redirect when a response cannot be safely sanitized."""
    responses = {
        "direct_buy_advice": (
            "I can't give a personalized buy instruction, but I can walk through the stock's "
            "price, fundamentals, forecast probabilities, and portfolio fit so you can decide."
        ),
        "direct_sell_advice": (
            "I can't give a personalized sell instruction, but I can review performance, "
            "forecast outlook, and concentration risk for that holding."
        ),
        "direct_hold_advice": (
            "I can't tell you to hold, but I can summarize recent performance, forecast, "
            "and how the position lines up with your risk profile."
        ),
        "direct_avoid_instruction": (
            "I can't tell you to avoid a stock, but I can review its retrieved fundamentals, "
            "price action, forecast, and key risks."
        ),
        "direct_trade_instruction": (
            "I can't issue a trade instruction. Ask for an analysis of the symbol, forecast, "
            "or how it fits your portfolio and I'll use live Basarat data."
        ),
        "allocation_instruction": (
            "I can't set allocation percentages, but I can show your current weights, "
            "sector exposure, and concentration so you can decide."
        ),
        "amount_instruction": (
            "I can't specify investment amounts, but I can explain position sizing concepts "
            "and how risk links to portfolio concentration."
        ),
        "percentage_instruction": (
            "I can't specify percentage allocations, but I can show current portfolio weights "
            "and sector concentrations."
        ),
        "guaranteed_return": (
            "No investment has guaranteed returns. I can explain forecast probabilities and "
            "historical volatility so you can judge risk versus reward."
        ),
        "guaranteed_profit": (
            "There are no guaranteed profits. I can help interpret forecasts, technicals, "
            "and fundamentals as probabilistic signals."
        ),
        "necessity_buy": (
            "You're not obligated to buy. I can help evaluate whether a stock matches your "
            "stated risk profile and goals."
        ),
        "necessity_sell": (
            "You're not obligated to sell. I can help assess whether selling aligns with "
            "your thesis and risk limits."
        ),
        "personalized_recommendation": (
            "I can't pick stocks for you personally, but I can analyze candidates against "
            "your risk profile, sector preferences, and live market data."
        ),
        "direct_buy_request": (
            "I can't make buy decisions for you. Ask me to analyze a symbol's fundamentals, "
            "technicals, forecast, or portfolio fit."
        ),
        "direct_sell_request": (
            "I can't make sell decisions for you. Ask me to review performance, forecast, "
            "or concentration for a holding."
        ),
        "entry_price_instruction": (
            "I can't set entry prices, but I can show current levels, ranges, and forecast "
            "probabilities from retrieved data."
        ),
        "exit_price_instruction": (
            "I can't set exit prices, but I can show model outlook and risk metrics from "
            "retrieved Basarat data."
        ),
        "timing_instruction": (
            "I can't time the market for you, but I can share the near-term forecast horizon "
            "and what the model currently suggests."
        ),
        "default": (
            "I provide educational decision-support for PSX stocks, portfolios, forecasts, "
            "and Basarat features — not personalized trade instructions. What would you like to analyze?"
        ),
    }
    return responses.get(violation_type, responses["default"])
