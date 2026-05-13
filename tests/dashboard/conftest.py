"""Per-blueprint conftest for the dashboard tests.

Same pattern as ``tests/maintenance/conftest.py``: bump the
``ServiceTicketFactory`` number sequence so dashboard tests don't
collide with explicit-number fixtures elsewhere in the suite.
"""

from __future__ import annotations

import pytest

from tests.factories import ServiceTicketFactory

_BUMPED = False


@pytest.fixture(scope="session", autouse=True)
def _skip_ticket_sequence_past_test_pins() -> None:
    global _BUMPED  # noqa: PLW0603
    if not _BUMPED:
        ServiceTicketFactory.reset_sequence(2_000_000)
        _BUMPED = True
