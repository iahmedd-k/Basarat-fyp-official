"""Deterministic article deduplication.

Strategy:
  1. Normalise URL (strip query params, trailing slash, lower-case scheme/host).
  2. Normalise title (lower-case, collapse whitespace, strip punctuation).
  3. Compute content_hash = SHA-256(normalised_title || "||" || normalised_url).
  4. Check existing content_hash values in DB before insertion.

If two articles from different legitimate sources are substantially different
in content, both are kept.  We only skip when the hash already exists.
"""

import hashlib
import re
from urllib.parse import urlparse, urlunparse


def normalise_url(url: str) -> str:
    """Lower-case scheme+host, drop query+fragment, strip trailing slash."""
    p = urlparse(url)
    normalised = urlunparse((p.scheme.lower(), p.netloc.lower(), p.path.rstrip("/"), "", "", ""))
    return normalised


def normalise_title(title: str) -> str:
    """Lower-case, collapse whitespace, strip non-alphanumeric."""
    text = title.lower().strip()
    text = re.sub(r"[^a-z0-9\s]", " ", text)
    text = re.sub(r"\s+", " ", text)
    return text.strip()


def compute_content_hash(title: str, url: str) -> str:
    """Return SHA-256 hex digest for deterministic dedup."""
    norm_title = normalise_title(title)
    norm_url = normalise_url(url)
    raw = f"{norm_title}||{norm_url}"
    return hashlib.sha256(raw.encode()).hexdigest()


def is_duplicate(content_hash: str, existing_hashes: set[str]) -> bool:
    """Check whether this hash was already seen in the current batch or DB."""
    return content_hash in existing_hashes
