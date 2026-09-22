"""Normalize cloud PostgreSQL URLs for the async API and sync migrations/tasks."""

from sqlalchemy.engine import URL, make_url


def _as_url(value: str) -> URL:
    url = make_url(value)
    if url.drivername == "postgres":
        url = url.set(drivername="postgresql")
    return url


def async_database_url(value: str) -> tuple[URL, dict]:
    """Return an asyncpg URL and compatible connection options."""
    url = _as_url(value)
    if url.drivername in {"postgresql", "postgresql+psycopg2", "postgresql+psycopg"}:
        url = url.set(drivername="postgresql+asyncpg")

    query = dict(url.query)
    connect_args: dict = {}
    sslmode = query.pop("sslmode", None)
    if not sslmode and (url.host or "").endswith((".supabase.co", ".pooler.supabase.com")):
        sslmode = "require"
    if sslmode:
        connect_args["ssl"] = sslmode
    if url.port == 6543:
        # Supabase/Supavisor transaction mode does not support prepared stmts.
        connect_args["statement_cache_size"] = 0
    return url.set(query=query), connect_args


def sync_database_url(async_url: str, configured_sync_url: str = "") -> URL:
    """Return a psycopg2 URL, deriving one from DATABASE_URL when omitted."""
    url = _as_url(configured_sync_url or async_url)
    if url.drivername in {"postgresql", "postgresql+asyncpg", "postgresql+psycopg"}:
        url = url.set(drivername="postgresql+psycopg2")
    if (
        (url.host or "").endswith((".supabase.co", ".pooler.supabase.com"))
        and "sslmode" not in url.query
    ):
        query = dict(url.query)
        query["sslmode"] = "require"
        url = url.set(query=query)
    return url
