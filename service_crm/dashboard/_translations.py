"""Translatable string registry for the dashboard blueprint.

Mirrors :mod:`service_crm.tickets._translations`. KPI tile labels and
panel headings declared with :func:`flask_babel.lazy_gettext` so
``pybabel extract`` picks them up.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

KPI_LABELS: dict[str, object] = {
    "active_clients": _l("Active clients"),
    "open_tickets": _l("Open tickets"),
    "overdue_tickets": _l("Overdue tickets"),
    "due_maintenance_week": _l("Due maintenance this week"),
    "tickets_waiting_parts": _l("Tickets waiting parts"),
    "technician_utilization": _l("Technician utilization"),
}

PANEL_LABELS: dict[str, object] = {
    "tickets_by_status": _l("Tickets by status"),
    "upcoming_maintenance": _l("Upcoming maintenance"),
    "recent_interventions": _l("Recent interventions"),
    "high_risk_machines": _l("High-risk machines"),
    "technician_load_week": _l("Technician load this week"),
    "my_queue": _l("My queue"),
    "my_overdue": _l("My overdue tickets"),
    "my_maintenance": _l("My maintenance tasks"),
}


def kpi_label(code: str) -> str:
    label = KPI_LABELS.get(code)
    return str(label) if label is not None else code


def panel_label(code: str) -> str:
    label = PANEL_LABELS.get(code)
    return str(label) if label is not None else code


__all__ = [
    "KPI_LABELS",
    "PANEL_LABELS",
    "kpi_label",
    "panel_label",
]
