import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.core.metrics import setup_prometheus_metrics


@pytest.mark.asyncio
async def test_metrics_endpoint_is_authenticated_and_reports_api_requests():
    app = FastAPI()

    @app.get("/health")
    async def health():
        return {"status": "ok"}

    setup_prometheus_metrics(app, username="scraper", password="test-password")

    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        health_response = await client.get("/health")
        unauthorized_response = await client.get("/metrics")
        metrics_response = await client.get(
            "/metrics",
            auth=("scraper", "test-password"),
        )

    assert health_response.status_code == 200
    assert unauthorized_response.status_code == 401
    assert metrics_response.status_code == 200
    assert "http_requests_total" in metrics_response.text
    assert "http_request_duration_seconds_bucket" in metrics_response.text
    assert 'handler="/health"' in metrics_response.text
