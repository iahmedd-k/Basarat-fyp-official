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
    if url.port == 6543 or "-pooler" in (url.host or "") or "pooler" in (url.host or ""):
        # Supabase/Neon transaction poolers do not support prepared statements.
        connect_args["statement_cache_size"] = 0
    return url.set(query=query), connect_args


def sync_database_url(async_url: str, configured_sync_url: str = "") -> URL:
    """Return a psycopg2 URL, deriving one from DATABASE_URL when omitted."""
    url = _as_url(configured_sync_url or async_url)
    if url.drivername in {"postgresql", "postgresql+asyncpg", "postgresql+psycopg"}:
        url = url.set(drivername="postgresql+psycopg2")
    query = dict(url.query)
    # Some providers (notably Neon) document `ssl=require`; psycopg2 expects
    # the libpq name `sslmode=require` instead.
    provider_ssl = query.pop("ssl", None)
    sslmode = query.get("sslmode") or provider_ssl
    if sslmode:
        query["sslmode"] = sslmode
    elif (url.host or "").endswith((".supabase.co", ".pooler.supabase.com", ".neon.tech")):
        query["sslmode"] = "require"
    url = url.set(query=query)
    return url
