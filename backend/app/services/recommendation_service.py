class RecommendationService:
    def __init__(self):
        self._weights = {"gru": 0.33, "technical": 0.33, "fundamental": 0.34}

    def get_recommendations(self, risk_profile: str = "moderate", sector: str | None = None) -> list[dict]:
        return []

    def get_stock_recommendation(self, symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "name": symbol.upper(),
            "signal": "hold",
            "confidence": 0.5,
            "target_price": None,
            "stop_loss": None,
            "reasoning": {},
            "technical_score": None,
            "fundamental_score": None,
            "sentiment_score": None,
        }

    def get_target_stop(self, symbol: str) -> dict:
        return {
            "symbol": symbol.upper(),
            "target_price": None,
            "stop_loss": None,
            "method": "technical_analysis",
        }

    def set_weights(self, gru: float, technical: float, fundamental: float) -> dict:
        self._weights = {"gru": gru, "technical": technical, "fundamental": fundamental}
        return self._weights
