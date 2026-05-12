"""Translatable string registry for ticket status / type / priority codes.

The ``code`` columns on :class:`TicketStatus`, :class:`TicketType`, and
:class:`TicketPriority` are stable English identifiers — but the labels
shown in the UI need to translate per the active locale.

This module declares each label with :func:`flask_babel.lazy_gettext`
under a known constant name. ``pybabel extract`` picks them up at build
time because they're function calls in a Python file (see
``babel.cfg``).

The lookup helpers (:func:`status_label`, :func:`type_label`,
:func:`priority_label`) are called from templates and routes:

    {{ status_label(ticket.status) }}      → "În lucru" (ro) / "In progress" (en)
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

# Status codes mirror service_crm.tickets.state.TicketStatus values.
STATUS_LABELS: dict[str, object] = {
    "new": _l("New"),
    "qualified": _l("Qualified"),
    "scheduled": _l("Scheduled"),
    "in_progress": _l("In progress"),
    "waiting_parts": _l("Waiting parts"),
    "monitoring": _l("Monitoring"),
    "completed": _l("Completed"),
    "closed": _l("Closed"),
    "cancelled": _l("Cancelled"),
}

# Status badge tone — used by templates to pick a colour class.
STATUS_TONE: dict[str, str] = {
    "new": "info",
    "qualified": "info",
    "scheduled": "warn",
    "in_progress": "good",
    "waiting_parts": "warn",
    "monitoring": "good",
    "completed": "good",
    "closed": "muted",
    "cancelled": "muted",
}

# Type codes seeded by the migration. Adding a new code requires a
# migration that also updates this dict.
TYPE_LABELS: dict[str, object] = {
    "incident": _l("Incident"),
    "preventive": _l("Preventive"),
    "commissioning": _l("Commissioning"),
    "warranty": _l("Warranty"),
    "installation": _l("Installation"),
    "audit": _l("Audit"),
}

# Priority codes seeded by the migration.
PRIORITY_LABELS: dict[str, object] = {
    "low": _l("Low"),
    "normal": _l("Normal"),
    "high": _l("High"),
    "urgent": _l("Urgent"),
}

PRIORITY_TONE: dict[str, str] = {
    "low": "muted",
    "normal": "info",
    "high": "warn",
    "urgent": "first-off",
}


def status_label(code: str) -> str:
    """Translated label for a status code; falls back to the code itself."""
    label = STATUS_LABELS.get(code)
    return str(label) if label is not None else code


def status_tone(code: str) -> str:
    """Badge tone class suffix for a status code."""
    return STATUS_TONE.get(code, "muted")


def type_label(code: str) -> str:
    """Translated label for a ticket type code; falls back to the code itself."""
    label = TYPE_LABELS.get(code)
    return str(label) if label is not None else code


def priority_label(code: str) -> str:
    """Translated label for a priority code; falls back to the code itself."""
    label = PRIORITY_LABELS.get(code)
    return str(label) if label is not None else code


def priority_tone(code: str) -> str:
    return PRIORITY_TONE.get(code, "muted")
