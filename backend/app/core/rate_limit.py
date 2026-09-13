from slowapi import Limiter
from slowapi.util import get_remote_address

from app.core.config import get_settings

settings = get_settings()


def rate_limit_key(request) -> str:
    """
    Per-IP by default. If a request is authenticated (has a resolved user
    on request.state, set by an auth dependency), key on user id instead,
    so one user can't dodge the limit by rotating IPs, and one IP with many
    users behind it (NAT, campus wifi) doesn't get punished as one caller.
    """
    user_id = getattr(request.state, "user_id", None)
    return user_id or get_remote_address(request)


limiter = Limiter(
    key_func=rate_limit_key,
    storage_uri=settings.REDIS_URL,
)