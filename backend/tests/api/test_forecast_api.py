"""API tests for forecasting endpoints."""

import pytest
from httpx import AsyncClient
from unittest.mock import patch, MagicMock


@pytest.mark.api
class TestForecastEndpoint:
    async def test_forecast_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/forecast/SYS")
        assert resp.status_code in (401, 403)

    async def test_forecast_invalid_horizon(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/SYS?horizon=INVALID", headers=auth_headers)
        assert resp.status_code == 422

    async def test_forecast_model_not_ready(self, client: AsyncClient, auth_headers):
        with patch("app.api.v1.forecast.artifacts") as mock_artifacts:
            mock_artifacts.model_ready = False
            resp = await client.get("/api/v1/forecast/SYS?horizon=1D", headers=auth_headers)
            assert resp.status_code == 503

    async def test_forecast_symbol_not_found(self, client: AsyncClient, auth_headers):
        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast") as mock_get_forecast:
            mock_artifacts.model_ready = True
            from app.ml.serving.inference import SymbolNotFoundError
            mock_get_forecast.side_effect = SymbolNotFoundError("Symbol 'NONEXISTENT' not found")

            resp = await client.get("/api/v1/forecast/NONEXISTENT", headers=auth_headers)
            assert resp.status_code == 404
            data = resp.json()
            assert "error" in data or "message" in data or "detail" in data

    async def test_forecast_success_mocked(self, client: AsyncClient, auth_headers):
        sample_result = {
            "symbol": "UBL",
            "horizon": "1W",
            "direction": "bullish",
            "confidence": 0.72,
            "top_class_probability": 72.0,
            "bullish_pct": 72.0,
            "bearish_pct": 18.0,
            "sideways_pct": 10.0,
            "as_of_date": "2026-09-18",
            "predicted_for_date": "2026-09-25",
            "current_price": 154.2,
            "volatility_14d": 0.012,
            "rsi": 38.5,
            "macd_hist": 0.78,
            "model_version": "v1.0",
            "gate_reason": "Confidence threshold met",
            "model_details": {
                "gru": {
                    "direction": "bullish",
                    "bullish_pct": 75.0,
                    "bearish_pct": 15.0,
                    "sideways_pct": 10.0,
                    "top_class_probability": 75.0,
                    "gap_pp": 60.0,
                },
                "xgb": {
                    "direction": "bullish",
                    "bullish_pct": 69.0,
                    "bearish_pct": 21.0,
                    "sideways_pct": 10.0,
                    "top_class_probability": 69.0,
                    "gap_pp": 48.0,
                },
            },
            "market_context": {
                "stock_return_5d": -0.012,
                "stock_return_20d": -0.05,
                "market_return_5d": -0.015,
                "market_return_20d": -0.038,
            }
        }

        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast", return_value=sample_result) as mock_get_forecast, \
             patch("app.api.v1.forecast.log_prediction"), \
             patch("app.api.v1.forecast.is_market_hours", return_value=True):
            mock_artifacts.model_ready = True

            resp = await client.get("/api/v1/forecast/UBL", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert set(data) == {
                "schema_version", "symbol", "name", "currency", "generated_at",
                "data_as_of", "freshness", "market_status", "horizon",
                "available_horizons", "price", "outlook", "levels",
                "recent_movement", "agreement", "upcoming_events",
                "track_record", "details",
            }
            assert data["schema_version"] == 1
            assert data["symbol"] == "UBL"
            assert data["name"] == "United Bank Limited"
            assert data["currency"] == "PKR"
            assert data["horizon"] == {
                "code": "1W",
                "trading_days": 5,
                "ends_on": "2026-09-25",
            }
            assert data["available_horizons"] == ["1D", "1W", "2W", "1M"]
            assert data["price"]["current"] == 154.2
            assert data["outlook"]["direction"] == "up"
            assert data["outlook"]["strength"] == "medium"
            assert data["levels"]["basis"] == "volatility_14d"
            assert data["levels"]["lower"] == pytest.approx(150.06, abs=0.01)
            assert data["levels"]["upper"] == pytest.approx(158.34, abs=0.01)
            assert data["recent_movement"] == {
                "stock_5d_pct": -1.2,
                "stock_20d_pct": -5.0,
                "market_5d_pct": -1.5,
                "market_20d_pct": -3.8,
                "vs_market": "weaker",
            }
            assert data["agreement"] == "full"
            assert data["details"]["up_probability_pct"] == 80.0
            assert data["details"]["down_probability_pct"] == 20.0
            assert data["details"]["models"] == [
                {"name": "gru", "direction": "up", "pct": 75.0},
                {"name": "xgb", "direction": "up", "pct": 69.0},
            ]
            assert data["details"]["indicators"] == {"rsi": 38.5, "macd_hist": 0.78}
            mock_get_forecast.assert_called_once_with("UBL", horizon="1W")

    async def test_neutral_forecast_uses_the_same_response_contract(self, client: AsyncClient, auth_headers):
        neutral_result = {
            "symbol": "SYS",
            "horizon": "1D",
            "direction": "sideways",
            "confidence": 0.5,
            "top_class_probability": 50.0,
            "bullish_pct": 33.0,
            "bearish_pct": 33.0,
            "sideways_pct": 34.0,
            "as_of_date": "2026-09-18",
            "predicted_for_date": "2026-09-19",
            "model_version": "ensemble",
            "gate_reason": "neutral_regime",
        }

        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast", return_value=neutral_result), \
             patch("app.api.v1.forecast.log_prediction"), \
             patch("app.api.v1.forecast.is_market_hours", return_value=False):
            mock_artifacts.model_ready = True

            resp = await client.get("/api/v1/forecast/SYS?horizon=1D", headers=auth_headers)

            assert resp.status_code == 200
            payload = resp.json()
            assert payload["outlook"]["direction"] == "sideways"
            assert payload["price"]["current"] is None
            assert payload["levels"]["lower"] is None
            assert payload["levels"]["upper"] is None


@pytest.mark.api
class TestForecastHistoryEndpoint:
    async def test_history_requires_auth(self, client: AsyncClient):
        resp = await client.get("/api/v1/forecast/SYS/history")
        assert resp.status_code in (401, 403)

    async def test_history_not_found(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/UNKNOWN_SYM/history", headers=auth_headers)
        assert resp.status_code == 404

    async def test_history_limit_validation(self, client: AsyncClient, auth_headers):
        resp = await client.get("/api/v1/forecast/SYS/history?limit=150", headers=auth_headers)
        assert resp.status_code == 422
