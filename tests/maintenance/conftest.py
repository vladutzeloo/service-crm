"""Per-blueprint conftest for the maintenance tests.

Skips ahead of the ``ServiceTicketFactory`` sequence so any
factory-created tickets in this module land at high numbers and don't
collide with explicit-number tickets elsewhere (e.g.
``tests/tickets/test_models.py``'s ``number=42`` assertion).

The repo-wide ``tests/conftest.py`` SAVEPOINT pattern doesn't roll back
data committed via route-handler ``db.session.commit()`` calls (a known
limitation; see ``docs/v0.7-plan.md`` §6.6). Re-seating the factory
sequence makes the v0.7 test suite robust to that leakage.
"""

from __future__ import annotations

import pytest

from tests.factories import ServiceTicketFactory

_BUMPED = False


@pytest.fixture(scope="session", autouse=True)
def _skip_ticket_sequence_past_test_pins() -> None:
    """Bump the ticket-number sequence past pinned test values.

    Session-scoped + idempotent: only the first invocation actually
    reseats the sequence; later calls (e.g. from the planning
    blueprint's parallel conftest) are no-ops so the sequence keeps
    climbing.
    """
    global _BUMPED  # noqa: PLW0603 - one-shot session-scoped guard
    if not _BUMPED:
        ServiceTicketFactory.reset_sequence(900_000)
        _BUMPED = True
