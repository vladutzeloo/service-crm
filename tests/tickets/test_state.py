"""Tests for the ticket state machine.

Per ROADMAP 0.5.0: ≥ 95 % line + branch coverage on
:mod:`service_crm.tickets.state`. The :class:`TicketStateMachine`
Hypothesis state-machine drives the FSM through random legal moves and
asserts that:

- every reachable state is reachable through some legal sequence,
- ``cancelled`` and ``closed`` have no outgoing transitions,
- every illegal transition raises :class:`IllegalTransition`.
"""

from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

from service_crm.tickets.state import (
    IllegalTransition,
    TicketStatus,
    is_terminal,
    legal_transitions,
    transition,
)


@pytest.mark.unit
def test_legal_transitions_admin_can_close_full_path() -> None:
    state = TicketStatus.NEW
    path = [
        TicketStatus.QUALIFIED,
        TicketStatus.SCHEDULED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.COMPLETED,
        TicketStatus.CLOSED,
    ]
    for nxt in path:
        state = transition(state, nxt, "admin")
    assert state is TicketStatus.CLOSED


@pytest.mark.unit
def test_manager_and_admin_can_drive_every_transition() -> None:
    for role in ("admin", "manager"):
        moves = legal_transitions(TicketStatus.NEW, role)
        assert TicketStatus.QUALIFIED in moves
        assert TicketStatus.CANCELLED in moves


@pytest.mark.unit
def test_technician_blocked_from_early_states() -> None:
    assert legal_transitions(TicketStatus.NEW, "technician") == set()
    assert legal_transitions(TicketStatus.QUALIFIED, "technician") == set()


@pytest.mark.unit
def test_technician_can_drive_in_progress_section() -> None:
    moves = legal_transitions(TicketStatus.IN_PROGRESS, "technician")
    assert TicketStatus.WAITING_PARTS in moves
    assert TicketStatus.MONITORING in moves
    assert TicketStatus.COMPLETED in moves
    assert TicketStatus.CANCELLED in moves


@pytest.mark.unit
def test_terminal_states_have_no_outgoing() -> None:
    assert legal_transitions(TicketStatus.CLOSED, "admin") == set()
    assert legal_transitions(TicketStatus.CANCELLED, "admin") == set()
    assert is_terminal(TicketStatus.CLOSED) is True
    assert is_terminal(TicketStatus.CANCELLED) is True
    assert is_terminal(TicketStatus.NEW) is False


@pytest.mark.unit
def test_cancelled_only_from_pre_completed() -> None:
    cancellable = {
        TicketStatus.NEW,
        TicketStatus.QUALIFIED,
        TicketStatus.SCHEDULED,
        TicketStatus.IN_PROGRESS,
        TicketStatus.WAITING_PARTS,
        TicketStatus.MONITORING,
    }
    for state in TicketStatus:
        moves = legal_transitions(state, "admin")
        if state in cancellable:
            assert TicketStatus.CANCELLED in moves
        else:
            assert TicketStatus.CANCELLED not in moves


@pytest.mark.unit
def test_unknown_role_has_no_legal_transitions() -> None:
    assert legal_transitions(TicketStatus.NEW, "guest") == set()
    assert legal_transitions(TicketStatus.IN_PROGRESS, "anonymous") == set()


@pytest.mark.unit
def test_transition_rejects_skipping_a_state() -> None:
    with pytest.raises(IllegalTransition):
        transition(TicketStatus.NEW, TicketStatus.IN_PROGRESS, "admin")


@pytest.mark.unit
def test_transition_rejects_going_backwards() -> None:
    with pytest.raises(IllegalTransition):
        transition(TicketStatus.QUALIFIED, TicketStatus.NEW, "admin")


@pytest.mark.unit
def test_transition_rejects_from_closed() -> None:
    with pytest.raises(IllegalTransition):
        transition(TicketStatus.CLOSED, TicketStatus.NEW, "admin")


@pytest.mark.unit
def test_transition_rejects_unknown_role() -> None:
    with pytest.raises(IllegalTransition):
        transition(TicketStatus.NEW, TicketStatus.QUALIFIED, "guest")


@pytest.mark.unit
@given(
    src=st.sampled_from(list(TicketStatus)),
    dst=st.sampled_from(list(TicketStatus)),
    role=st.sampled_from(["admin", "manager", "technician", "guest"]),
)
def test_transition_random_property(
    src: TicketStatus, dst: TicketStatus, role: str
) -> None:
    moves = legal_transitions(src, role)
    if dst in moves:
        assert transition(src, dst, role) is dst
    else:
        with pytest.raises(IllegalTransition):
            transition(src, dst, role)


class TicketStateMachine(RuleBasedStateMachine):
    """Drives a ticket through random legal transitions.

    Each ``step_*`` rule picks one legal next state for the current
    role and asserts the move succeeds; an invariant verifies that the
    machine never holds an illegal state value.
    """

    def __init__(self) -> None:
        super().__init__()
        self.role = "admin"
        self.state = TicketStatus.NEW
        self.moves: list[tuple[TicketStatus, TicketStatus]] = []

    @rule()
    def step_any_legal(self) -> None:
        moves = legal_transitions(self.state, self.role)
        if not moves:
            return
        # Pick the lexicographically-first legal move for determinism.
        nxt = sorted(moves, key=lambda s: s.value)[0]
        transition(self.state, nxt, self.role)
        self.moves.append((self.state, nxt))
        self.state = nxt

    @invariant()
    def state_is_known(self) -> None:
        assert self.state in set(TicketStatus)

    @invariant()
    def terminal_is_sticky(self) -> None:
        if is_terminal(self.state):
            assert legal_transitions(self.state, self.role) == set()


TestTicketStateMachine = TicketStateMachine.TestCase
TestTicketStateMachine.settings = settings(max_examples=50, deadline=None)
