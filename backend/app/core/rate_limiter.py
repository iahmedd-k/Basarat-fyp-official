from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from app.core.config import get_settings


def _get_client_ip(request: Request) -> str:
    forwarded = request.headers.get("X-Forwarded-For")
    peer_ip = request.client.host if request.client else "unknown"
    if forwarded and peer_ip in get_settings().TRUSTED_PROXY_IPS:
        return forwarded.split(",")[0].strip()
    return peer_ip or get_remote_address(request)


def get_user_id_or_ip(request: Request) -> str:
    """Get user ID from auth token if available, otherwise use IP."""
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        try:
            from app.core.security import decode_token
            token = auth_header.split(" ")[1]
            payload = decode_token(token)
            if payload and payload.get("type") == "access":
                return f"user:{payload.get('sub', 'unknown')}"
        except Exception:
            pass
    return _get_client_ip(request)


limiter = Limiter(key_func=get_user_id_or_ip)


def add_rate_limiting(app: FastAPI) -> None:
    app.state.limiter = limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
