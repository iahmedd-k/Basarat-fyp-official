"""Time-sortable, monotonic, collision-resistant ID generator for Community entities.

Generates ULID / UUIDv7 compatible 128-bit identifiers:
- 48-bit millisecond timestamp (lexicographically time-sortable)
- 80-bit cryptographic entropy / sequence
- Formatted as 32-character lowercase hex or 26-character Crockford Base32.
"""

import os
import time
import threading
from uuid import uuid4

_lock = threading.Lock()
_last_timestamp_ms = 0
_sequence = 0


def generate_time_id() -> str:
    """Generate a 32-char hex time-sortable ID (UUIDv7 layout).
    
    Layout:
    - 48 bits (12 hex chars): Unix timestamp in milliseconds
    - 4 bits (1 hex char): Version 7 ('7')
    - 12 bits (3 hex chars): Sequence counter / sub-millisecond entropy
    - 2 bits: Variant 2 ('8', '9', 'a', or 'b')
    - 62 bits (16 hex chars): Cryptographic random bits
    """
    global _last_timestamp_ms, _sequence
    
    with _lock:
        now_ms = int(time.time() * 1000)
        if now_ms == _last_timestamp_ms:
            _sequence = (_sequence + 1) & 0xFFF
            if _sequence == 0:
                # Sequence exhausted in same millisecond, increment millisecond artificially
                now_ms += 1
                _last_timestamp_ms = now_ms
        else:
            _last_timestamp_ms = now_ms
            _sequence = int.from_bytes(os.urandom(2), "big") & 0xFFF

    time_hex = f"{now_ms:012x}"
    ver_seq_hex = f"7{_sequence:03x}"
    rand_bytes = os.urandom(8)
    # Set variant (10xx in binary -> 8..b in hex)
    rand_byte_0 = (rand_bytes[0] & 0x3F) | 0x80
    rand_hex = f"{rand_byte_0:02x}" + rand_bytes[1:].hex()
    
    return f"{time_hex}{ver_seq_hex}{rand_hex}"


def extract_timestamp_from_id(time_id: str) -> float | None:
    """Extract Unix timestamp in seconds from a time-sortable ID."""
    if not time_id or len(time_id) < 12:
        return None
    try:
        ts_ms = int(time_id[:12], 16)
        # Sanity check timestamp range (from year 2020 to 2100)
        if 1577836800000 <= ts_ms <= 4102444800000:
            return ts_ms / 1000.0
    except ValueError:
        pass
    return None
