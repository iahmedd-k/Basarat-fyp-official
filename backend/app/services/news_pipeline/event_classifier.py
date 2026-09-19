"""Rule-based event classification for news articles.

Classifies articles into one of the predefined event types using
keyword matching.  Designed to be replaceable with a more sophisticated
classifier later.
"""

import re

# ── Event type definitions with trigger patterns ──────────────────────────

_EVENT_RULES: list[tuple[str, list[str]]] = [
    ("earnings", [
        r"\bearnings?\b", r"\bprofit\b", r"\brevenue\b", r"\bloss\b",
        r"\bnet income\b", r"\bgross margin\b", r"\beps\b",
        r"\bquarterly result\b", r"\bannual result\b", r"\bhalf.?year",
        r"\bfinancial result\b", r"\bfinancial statement",
        r"\bsurprise\b", r"\bbeats?\b", r"\bmiss(es|ed)?\b",
        r"\b(above|below|ahead of|behind)\s+(expectations|estimate|forecast)",
        r"\bexceeded?\s+(expectations|estimate|forecast)", r"\bestimates?\b",
    ]),
    ("dividend", [
        r"\bdividend\b", r"\bfinal dividend\b", r"\binterim dividend\b",
        r"\bcash dividend\b", r"\bspecial dividend\b", r"\bbonus\b",
        r"\bright\b", r"\bissue\b",
    ]),
    ("monetary_policy", [
        r"\bmonetary policy\b", r"\bpolicy rate\b",
        r"\binterest rate\b", r"\bcash reserve\b", r"\bopen market\b",
    ]),
    ("interest_rate", [
        r"\binterest rate\b", r"\bpolicy rate\b", r"\brate cut\b",
        r"\brate hike\b", r"\brate hold\b",
        r"\bsbp\b.*\brate\b", r"\bbasis point\b",
    ]),
    ("circular_debt", [
        r"\bcircular debt\b", r"\binter.?corporate\s+debt\b",
        r"\bpower\b.*\barrears\b", r"\benergy\b.*\barrears\b",
        r"\bcapacity payments?\b", r"\btariff differential\b",
        r"\bcede\b", r"\bpower\b.*\bdues?\b", r"\bgas\b.*\bdues?\b",
    ]),
    ("imf", [
        r"\bimf\b", r"\bprogramme\b", r"\bstand.?by\b",
        r"\breview\b", r"\btranche\b", r"\bextended fund\b",
        r"\bdisburs", r"\bfund\s+board\b", r"\bdebt\s+sustainab",
        r"\bprior action",
    ]),
    ("block_order", [
        r"\bblock orders?\b", r"\binstitutional\s+(buy|sell|trading|interest)",
        r"\bforeign\s+(buying|selling|inflow|outflow|participation)",
        r"\blocal\s+(buying|selling)", r"\bcross\s+trade", r"\bbulk\s+(buy|sell)",
        r"\bproprietary\s+trading", r"\bresource\s+flow",
    ]),
    ("acquisition", [
        r"\bacqui[sz]", r"\bacquire[sd]?\b", r"\btakeover\b",
        r"\bbid\b", r"\boffer\b", r"\bpurchase\b",
    ]),
    ("merger", [
        r"\bmerger\b", r"\bamalgam", r"\bcombine\b",
    ]),
    ("contract", [
        r"\bcontract\b", r"\border\b", r"\bagreement\b",
        r"\bmemorandum\b", r"\bmo[u]?[au]\b", r"\bjoint venture\b",
    ]),
    ("regulatory_action", [
        r"\bsecp\b", r"\bregulat", r"\bsanction",
        r"\bpenalty\b", r"\bfine\b", r"\bsuspend", r"\bcompliance\b",
        r"\benforcement\b",
    ]),
    ("oil_price", [
        r"\boil price\b", r"\bcrude\b", r"\bpetroleum\b",
        r"\bbarrel\b", r"\bopec\b", r"\b Brent\b", r"\bWTI\b",
    ]),
    ("currency", [
        r"\brupee\b", r"\bpkr\b", r"\bdollar\b", r"\bforex\b",
        r"\bexchange rate\b", r"\bcurrency\b", r"\bdevaluat",
    ]),
    ("expansion", [
        r"\bexpansion\b", r"\bnew plant\b", r"\bcapacity\b",
        r"\bnew product\b", r"\blaunch\b", r"\bcommission\b",
    ]),
    ("management_change", [
        r"\bceo\b", r"\bchairman\b", r"\bdirector\b", r"\bappointment\b",
        r"\bresign", r"\bremoval\b", r"\bexecutive\b", r"\bmanagement\b",
    ]),
    ("litigation", [
        r"\bcourt\b", r"\blawsuit\b", r"\blitigation\b", r"\bcase\b",
        r"\bdispute\b", r"\btribunal\b", r"\bappellate\b",
    ]),
]

# Compile once at import time
_COMPILED_RULES: list[tuple[str, list[re.Pattern]]] = [
    (event_type, [re.compile(p, re.IGNORECASE) for p in patterns])
    for event_type, patterns in _EVENT_RULES
]


def classify_event(title: str, summary: str | None = None) -> str:
    """Classify a single article into an event type.

    Returns the first matching event type, or 'other' if none match.
    Priority is defined by the order in _EVENT_RULES.
    """
    text = f"{title} {summary or ''}"
    for event_type, patterns in _COMPILED_RULES:
        for pattern in patterns:
            if pattern.search(text):
                return event_type
    return "other"


def classify_articles(articles: list[dict]) -> list[dict]:
    """Classify a batch of articles. Adds 'event_type' to each dict."""
    for article in articles:
        article["event_type"] = classify_event(
            article.get("title", ""),
            article.get("summary"),
        )
    return articles
