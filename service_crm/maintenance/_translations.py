"""Translatable string registry for the maintenance blueprint.

Mirrors :mod:`service_crm.tickets._translations`. Status codes stay
stable English; UI labels translate via this registry so ``pybabel
extract`` picks them up.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

from .models import TaskStatus

TASK_STATUS_LABELS: dict[str, object] = {
    TaskStatus.PENDING: _l("Pending"),
    TaskStatus.DONE: _l("Done"),
    TaskStatus.ESCALATED: _l("Escalated to ticket"),
}

TASK_STATUS_TONES: dict[str, str] = {
    TaskStatus.PENDING: "warning",
    TaskStatus.DONE: "success",
    TaskStatus.ESCALATED: "info",
}


def task_status_label(code: str) -> str:
    label = TASK_STATUS_LABELS.get(code)
    return str(label) if label is not None else code


def task_status_tone(code: str) -> str:
    return TASK_STATUS_TONES.get(code, "default")


__all__ = [
    "TASK_STATUS_LABELS",
    "TASK_STATUS_TONES",
    "task_status_label",
    "task_status_tone",
]
