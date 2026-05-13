"""Translation registry for the planning blueprint."""

from __future__ import annotations

import pytest
from flask import Flask

from service_crm.planning._translations import (
    ASSIGNMENT_TARGET_LABELS,
    assignment_target_code,
    assignment_target_label,
)


def test_assignment_target_labels_present() -> None:
    assert set(ASSIGNMENT_TARGET_LABELS) == {"ticket", "intervention", "both"}


@pytest.mark.parametrize("code", ["ticket", "intervention", "both"])
def test_assignment_target_label_resolves(code: str, app: Flask) -> None:
    with app.test_request_context():
        assert assignment_target_label(code)


def test_assignment_target_label_unknown_passthrough() -> None:
    assert assignment_target_label("bogus") == "bogus"


def test_assignment_target_code_resolution() -> None:
    ticket = b"\x01" * 16
    intervention = b"\x02" * 16
    assert assignment_target_code(ticket_id=ticket, intervention_id=None) == "ticket"
    assert assignment_target_code(ticket_id=None, intervention_id=intervention) == "intervention"
    assert assignment_target_code(ticket_id=ticket, intervention_id=intervention) == "both"
    # Defaults to "ticket" when both None (caller should validate first).
    assert assignment_target_code(ticket_id=None, intervention_id=None) == "ticket"
