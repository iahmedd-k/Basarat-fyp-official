class SentimentService:
    def __init__(self):
        pass

    def get_stock_sentiment(self, symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "score": 0.0,
            "label": "neutral",
            "article_count": 0,
            "trend": "stable",
        }

    def get_market_sentiment(self) -> dict:
        return {
            "market_mood": "neutral",
            "advancing": 0,
            "declining": 0,
            "unchanged": 0,
            "advance_decline_ratio": 1.0,
            "overall_score": 0.0,
        }
