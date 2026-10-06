from secrets import compare_digest
from time import perf_counter

from fastapi import Depends, FastAPI, HTTPException
from fastapi.responses import Response
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from prometheus_client import CONTENT_TYPE_LATEST, Counter, Histogram, generate_latest
from starlette.types import ASGIApp, Receive, Scope, Send


HTTP_REQUESTS = Counter(
    "http_requests",
    "Total number of HTTP requests handled by the API.",
    ("handler", "method", "status"),
)
HTTP_REQUEST_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds.",
    ("handler", "method"),
)
METRICS_SECURITY = HTTPBasic()
KNOWN_METHODS = {"DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"}


class MetricsMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return

        started_at = perf_counter()
        status_code = 500

        async def record_response_start(message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, record_response_start)
        finally:
            route = scope.get("route")
            handler = getattr(route, "path_format", None) or getattr(route, "path", None)
            handler = handler or "unmatched"
            method = scope.get("method", "").upper()
            method = method if method in KNOWN_METHODS else "OTHER"
            HTTP_REQUESTS.labels(handler, method, str(status_code)).inc()
            HTTP_REQUEST_DURATION.labels(handler, method).observe(
                perf_counter() - started_at
            )


def setup_prometheus_metrics(app: FastAPI, username: str, password: str) -> None:
    app.add_middleware(MetricsMiddleware)

    @app.get("/metrics", include_in_schema=False)
    async def metrics_endpoint(
        credentials: HTTPBasicCredentials = Depends(METRICS_SECURITY),
    ) -> Response:
        if not (
            compare_digest(credentials.username, username)
            and compare_digest(credentials.password, password)
        ):
            raise HTTPException(
                status_code=401,
                detail="Invalid metrics credentials",
                headers={"WWW-Authenticate": 'Basic realm="metrics"'},
            )
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST,
        )
