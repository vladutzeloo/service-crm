"""Translatable string registry for the planning blueprint."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

ASSIGNMENT_TARGET_LABELS: dict[str, object] = {
    "ticket": _l("Ticket"),
    "intervention": _l("Intervention"),
    "both": _l("Ticket + intervention"),
}


def assignment_target_label(code: str) -> str:
    label = ASSIGNMENT_TARGET_LABELS.get(code)
    return str(label) if label is not None else code


def assignment_target_code(*, ticket_id: bytes | None, intervention_id: bytes | None) -> str:
    if ticket_id is not None and intervention_id is not None:
        return "both"
    if intervention_id is not None:
        return "intervention"
    return "ticket"


__all__ = [
    "ASSIGNMENT_TARGET_LABELS",
    "assignment_target_code",
    "assignment_target_label",
]
