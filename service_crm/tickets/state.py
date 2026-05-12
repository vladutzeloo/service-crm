"""Ticket state machine — pure Python.

The state machine has no database dependencies, which lets the
``hypothesis.stateful`` test in ``tests/tickets/test_state.py`` exercise
every legal and illegal combination without a session.

Lifecycle per [`service-domain.md`](../../docs/service-domain.md):

    new → qualified → scheduled → in_progress → waiting_parts →
    monitoring → completed → closed

``cancelled`` is reachable from any pre-``completed`` state.

The role argument is the actor's role name (``"admin"``, ``"manager"``,
``"technician"``). Admins and managers can drive every transition;
technicians can only act on tickets already assigned to the
in-progress part of the lifecycle.
"""

from __future__ import annotations

from enum import StrEnum


class TicketStatus(StrEnum):
    """Stable English status codes. UI labels are looked up via
    :mod:`service_crm.tickets._translations`."""

    NEW = "new"
    QUALIFIED = "qualified"
    SCHEDULED = "scheduled"
    IN_PROGRESS = "in_progress"
    WAITING_PARTS = "waiting_parts"
    MONITORING = "monitoring"
    COMPLETED = "completed"
    CLOSED = "closed"
    CANCELLED = "cancelled"


class IllegalTransition(ValueError):
    """Raised when the requested transition isn't allowed for the current
    state / role combination."""


# Forward edges (excluding ``cancelled``) — strict linear progression with
# two side-routes for waiting-parts and monitoring back into in-progress.
_FORWARD: dict[TicketStatus, frozenset[TicketStatus]] = {
    TicketStatus.NEW: frozenset({TicketStatus.QUALIFIED}),
    TicketStatus.QUALIFIED: frozenset({TicketStatus.SCHEDULED}),
    TicketStatus.SCHEDULED: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.IN_PROGRESS: frozenset(
        {
            TicketStatus.WAITING_PARTS,
            TicketStatus.MONITORING,
            TicketStatus.COMPLETED,
        }
    ),
    TicketStatus.WAITING_PARTS: frozenset({TicketStatus.IN_PROGRESS}),
    TicketStatus.MONITORING: frozenset(
        {TicketStatus.IN_PROGRESS, TicketStatus.COMPLETED}
    ),
    TicketStatus.COMPLETED: frozenset({TicketStatus.CLOSED}),
    TicketStatus.CLOSED: frozenset(),
    TicketStatus.CANCELLED: frozenset(),
}


# States from which cancellation is allowed (anything pre-``completed``).
_CANCELLABLE: frozenset[TicketStatus] = frozenset(
    {
        TicketStatus.NEW,
        TicketStatus.QUALIFIED,
        TicketStatus.SCHEDULED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_PARTS,
        TicketStatus.MONITORING,
    }
)


# RBAC: which forward transitions are allowed for each role. Admin and
# manager can drive every transition; technician is limited to the
# in-progress section. Cancellation follows the same rules as the
# forward transition out of the source state.
_TECHNICIAN_ALLOWED_FROM: frozenset[TicketStatus] = frozenset(
    {
        TicketStatus.SCHEDULED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_PARTS,
        TicketStatus.MONITORING,
    }
)


def _role_allows(role: str, from_state: TicketStatus) -> bool:
    if role in {"admin", "manager"}:
        return True
    if role == "technician":
        return from_state in _TECHNICIAN_ALLOWED_FROM
    return False


def legal_transitions(from_state: TicketStatus, role: str) -> set[TicketStatus]:
    """Return the set of states the actor is allowed to move to from
    ``from_state``. Includes ``cancelled`` where applicable."""
    if not _role_allows(role, from_state):
        return set()
    moves: set[TicketStatus] = set(_FORWARD[from_state])
    if from_state in _CANCELLABLE:
        moves.add(TicketStatus.CANCELLED)
    return moves


def is_terminal(state: TicketStatus) -> bool:
    """Whether the state is a sink (``closed`` or ``cancelled``)."""
    return state in {TicketStatus.CLOSED, TicketStatus.CANCELLED}


def transition(
    from_state: TicketStatus, to_state: TicketStatus, role: str
) -> TicketStatus:
    """Verify the move is legal for ``role`` and return ``to_state``.

    Raises :class:`IllegalTransition` if the move would skip a stage, run
    backwards out of a terminal state, or exceed the actor's role.
    """
    if to_state not in legal_transitions(from_state, role):
        raise IllegalTransition(
            f"cannot transition {from_state.value!r} → {to_state.value!r} as {role!r}"
        )
    return to_state
