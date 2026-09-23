"""Verify the configured Redis URL can reach Upstash without exposing secrets."""

from __future__ import annotations

import sys
from pathlib import Path
from uuid import uuid4
from urllib.parse import urlparse

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import redis

from app.core.config import get_settings


def main() -> int:
    settings = get_settings()
    parsed = urlparse(settings.REDIS_URL)
    if not parsed.hostname or not parsed.hostname.endswith(".upstash.io"):
        print("FAIL: REDIS_URL is not configured for an Upstash host.")
        return 1
    if parsed.scheme != "rediss":
        print("FAIL: Upstash REDIS_URL must use TLS (rediss://).")
        return 1

    client = redis.Redis.from_url(
        settings.REDIS_URL,
        socket_connect_timeout=8,
        socket_timeout=8,
        decode_responses=True,
    )
    key = f"basarat:upstash-connection-check:{uuid4().hex}"
    operation = "PING"
    try:
        if not client.ping():
            print("FAIL: Upstash did not return PONG.")
            return 1
        operation = "SET"
        client.set(key, "connection-ok", ex=60)
        operation = "GET"
        if client.get(key) != "connection-ok":
            print("FAIL: Upstash write/read check returned the wrong value.")
            return 1
        operation = "DELETE"
        if client.delete(key) != 1:
            print("FAIL: Upstash delete check did not remove the temporary key.")
            return 1
        print(f"PASS: Upstash PING, SET, GET, and DELETE succeeded ({parsed.hostname}).")
        return 0
    except Exception as exc:
        # Do not print exception text: client errors can include connection details.
        print(f"FAIL: Upstash {operation} raised {type(exc).__name__}.")
        return 1
    finally:
        try:
            client.delete(key)
            client.close()
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
