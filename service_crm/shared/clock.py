"""Mockable wall clock.

Always import ``now`` from here, never call ``datetime.now`` directly.
The fixture ``frozen_clock`` in ``tests/conftest.py`` patches ``_now``
so deterministic timestamps are one line away.
"""

from __future__ import annotations

from datetime import UTC, datetime


def now() -> datetime:
    return _now()


def _now() -> datetime:
    """Indirection seam for tests; patch this, not ``now``."""
    return datetime.now(UTC)
