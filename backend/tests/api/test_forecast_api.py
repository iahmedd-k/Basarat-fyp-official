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
            "symbol": "SYS",
            "horizon": "1D",
            "direction": "bullish",
            "confidence": 0.72,
            "top_class_probability": 72.0,
            "bullish_pct": 72.0,
            "bearish_pct": 18.0,
            "sideways_pct": 10.0,
            "as_of_date": "2026-09-18",
            "predicted_for_date": "2026-09-19",
            "model_version": "v1.0",
            "gate_reason": "Confidence threshold met",
            "model_details": {
                "gru": {
                    "direction": "bullish",
                    "bullish_pct": 75.0,
                    "bearish_pct": 15.0,
                    "sideways_pct": 10.0,
                    "gap_pp": 60.0,
                },
                "xgb": {
                    "direction": "bullish",
                    "bullish_pct": 69.0,
                    "bearish_pct": 21.0,
                    "sideways_pct": 10.0,
                    "gap_pp": 48.0,
                },
            },
            "market_context": {
                "kse100_trend": "bullish",
                "volatility_regime": "low",
            }
        }

        with patch("app.api.v1.forecast.artifacts") as mock_artifacts, \
             patch("app.api.v1.forecast.get_forecast", return_value=sample_result), \
             patch("app.api.v1.forecast.log_prediction"):
            mock_artifacts.model_ready = True

            resp = await client.get("/api/v1/forecast/SYS?horizon=1D", headers=auth_headers)
            assert resp.status_code == 200
            data = resp.json()

            assert data["symbol"] == "SYS"
            assert data["horizon"] == "1D"
            assert data["direction"] == "bullish"
            assert data["signal_rating"] == "Strong Buy"
            assert "probabilities" in data
            assert data["probabilities"]["bullish"] == 72.0
            assert "models" in data
            assert "gru" in data["models"]
            assert "xgb" in data["models"]


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
