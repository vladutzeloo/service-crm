"""Tiny ULID implementation + a SQLAlchemy ``TypeDecorator`` that stores
ULIDs as native ``UUID`` on Postgres and ``BLOB(16)`` on SQLite.

ULID is timestamp-prefixed so the resulting IDs sort by creation order,
which keeps B-tree indexes hot. We use Crockford's base32 alphabet for
the human-readable encoding, the same as the spec at https://github.com/ulid/spec.

Why hand-roll instead of pulling in ``python-ulid``: the architecture
plan §3.3 commits to ULID-as-UUID/BLOB(16) only, and a 60-line file is
cheaper than a transitive dep audit.
"""

from __future__ import annotations

import secrets
from typing import Any

from sqlalchemy.dialects.postgresql import UUID as PG_UUID
from sqlalchemy.engine.interfaces import Dialect
from sqlalchemy.types import BINARY, TypeDecorator

from . import clock

_CROCKFORD = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
_DECODE = {ch: i for i, ch in enumerate(_CROCKFORD)}

RAW_BYTES = 16
TIME_BYTES = 6
RAND_BYTES = 10
ENCODED_LEN = 26
BITS_PER_CHAR = 5
CHAR_MASK = 0x1F


def new() -> bytes:
    """Generate a new ULID as 16 raw bytes (6-byte time + 10-byte random)."""
    ts_ms = int(clock.now().timestamp() * 1000)
    time_bytes = ts_ms.to_bytes(TIME_BYTES, "big")
    rand_bytes = secrets.token_bytes(RAND_BYTES)
    return time_bytes + rand_bytes


def encode(raw: bytes) -> str:
    """Encode 16 raw bytes as a 26-char Crockford base32 string."""
    if len(raw) != RAW_BYTES:
        raise ValueError(f"ULID must be {RAW_BYTES} bytes, got {len(raw)}")
    n = int.from_bytes(raw, "big")
    out = []
    for _ in range(ENCODED_LEN):
        out.append(_CROCKFORD[n & CHAR_MASK])
        n >>= BITS_PER_CHAR
    return "".join(reversed(out))


def decode(s: str) -> bytes:
    """Decode a 26-char ULID string back to its 16 raw bytes."""
    if len(s) != ENCODED_LEN:
        raise ValueError(f"ULID must be {ENCODED_LEN} chars, got {len(s)}")
    n = 0
    for ch in s.upper():
        try:
            n = (n << BITS_PER_CHAR) | _DECODE[ch]
        except KeyError as exc:
            raise ValueError(f"invalid ULID character: {ch!r}") from exc
    return n.to_bytes(RAW_BYTES, "big")


class ULID(TypeDecorator[bytes]):
    """SQLAlchemy column type for ULID values.

    Stored as ``UUID`` on Postgres (16-byte native UUID column) and
    ``BLOB(16)`` on SQLite. Values are always exposed to Python as raw
    ``bytes`` of length 16 — encode at the edge if you need the string.
    """

    impl = BINARY(16)
    cache_ok = True

    def load_dialect_impl(self, dialect: Dialect) -> Any:
        if dialect.name == "postgresql":
            return dialect.type_descriptor(PG_UUID(as_uuid=False))
        return dialect.type_descriptor(BINARY(16))

    def process_bind_param(self, value: bytes | None, dialect: Dialect) -> Any:
        if value is None:
            return None
        if len(value) != RAW_BYTES:
            raise ValueError(f"ULID must be {RAW_BYTES} bytes, got {len(value)}")
        if dialect.name == "postgresql":
            # Postgres native UUID expects a 32-char hex string.
            return value.hex()
        return value

    def process_result_value(self, value: Any, dialect: Dialect) -> bytes | None:
        if value is None:
            return None
        if dialect.name == "postgresql":
            # value comes back as a 32-char hex string when as_uuid=False.
            return bytes.fromhex(value.replace("-", ""))
        return bytes(value)
