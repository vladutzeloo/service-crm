"""Translatable label registry for the reports blueprint.

Per the v0.8 plan, CSV exports keep stable English ``code`` columns
and ship a separately translated ``label`` column so spreadsheet
pivots remain locale-independent. The labels here drive both the
HTML view and the CSV's ``label`` column.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

REPORT_LABELS: dict[str, object] = {
    "tickets_by_status": _l("Tickets by status"),
    "interventions_by_machine": _l("Interventions by machine"),
    "parts_used": _l("Parts used"),
    "maintenance_due_vs_completed": _l("Maintenance: due vs. completed"),
    "technician_workload": _l("Technician workload"),
    "repeat_issues": _l("Repeat-issue machines"),
}

REPORT_DESCRIPTIONS: dict[str, object] = {
    "tickets_by_status": _l("How many tickets are sitting in each status, bucketed by period."),
    "interventions_by_machine": _l("Field-job count and time spent, grouped by equipment."),
    "parts_used": _l("Quantity of each part consumed inside the window."),
    "maintenance_due_vs_completed": _l("Planned vs. actual maintenance throughput."),
    "technician_workload": _l("Interventions, minutes, and completion counts per technician."),
    "repeat_issues": _l("Equipment that opened more than one ticket inside the window."),
}

# Period bucket labels (day / week / month). Bucketing is chosen by
# window length in services.py; the labels stay constant.
PERIOD_LABELS: dict[str, object] = {
    "day": _l("Day"),
    "week": _l("Week"),
    "month": _l("Month"),
}


def report_label(code: str) -> str:
    label = REPORT_LABELS.get(code)
    return str(label) if label is not None else code


def report_description(code: str) -> str:
    label = REPORT_DESCRIPTIONS.get(code)
    return str(label) if label is not None else ""


def period_label(code: str) -> str:
    label = PERIOD_LABELS.get(code)
    return str(label) if label is not None else code


REPORT_CODES: tuple[str, ...] = (
    "tickets_by_status",
    "interventions_by_machine",
    "parts_used",
    "maintenance_due_vs_completed",
    "technician_workload",
    "repeat_issues",
)


__all__ = [
    "PERIOD_LABELS",
    "REPORT_CODES",
    "REPORT_DESCRIPTIONS",
    "REPORT_LABELS",
    "period_label",
    "report_description",
    "report_label",
]
