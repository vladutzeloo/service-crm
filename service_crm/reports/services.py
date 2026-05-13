"""Aggregation services for the reports blueprint.

Each report returns a ``ReportResult`` carrying:

- ``headers`` — translated column headers for the HTML and CSV views.
- ``rows`` — list of tuples (stable values; the route formats them).
- ``total_row`` — optional, rendered as a footer row in HTML and an
  extra line in CSV.

Period bucketing for the time-series reports uses:

- day for windows ≤ 31 days,
- week for windows 32-180 days,
- month for everything longer.

Buckets are computed in Python after the SQL pull. The reference
dataset (≤ 100k tickets) keeps this well inside the perf budget;
SQLite vs. Postgres ``date_trunc`` branching gets pushed to v0.9
hardening if the budget is missed.
"""

from __future__ import annotations

from collections import defaultdict
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth.models import User
from ..equipment.models import Equipment
from ..maintenance.models import (
    MaintenanceExecution,
    MaintenancePlan,
    MaintenanceTask,
)
from ..planning.models import Technician
from ..shared.date_window import DateWindow
from ..tickets.intervention_models import (
    PartMaster,
    ServiceIntervention,
    ServicePartUsage,
)
from ..tickets.models import ServiceTicket

PERIOD_DAY = "day"
PERIOD_WEEK = "week"
PERIOD_MONTH = "month"

# Window-length thresholds for the bucket picker.
_BUCKET_DAY_MAX_DAYS = 31
_BUCKET_WEEK_MAX_DAYS = 180


def choose_bucket(window: DateWindow) -> str:
    """Pick a bucket size based on window length."""
    days = window.days
    if days <= _BUCKET_DAY_MAX_DAYS:
        return PERIOD_DAY
    if days <= _BUCKET_WEEK_MAX_DAYS:
        return PERIOD_WEEK
    return PERIOD_MONTH


def bucket_for(day: date, bucket: str) -> date:
    """Snap ``day`` to the start of its bucket."""
    if bucket == PERIOD_DAY:
        return day
    if bucket == PERIOD_WEEK:
        return day - timedelta(days=day.weekday())
    if bucket == PERIOD_MONTH:
        return day.replace(day=1)
    raise ValueError(f"unknown bucket: {bucket!r}")  # pragma: no cover - guarded by choose_bucket


@dataclass(frozen=True)
class ReportResult:
    """Generic shape returned by every report function."""

    headers: list[str]
    rows: list[tuple[Any, ...]]
    total_row: tuple[Any, ...] | None = None
    bucket: str | None = None
    meta: dict[str, Any] = field(default_factory=dict)


def _to_naive_utc(d: date) -> datetime:
    return datetime(d.year, d.month, d.day)


# ── 1. tickets_by_status ─────────────────────────────────────────────────────


def tickets_by_status(
    session: Session,
    *,
    window: DateWindow,
    status_label: Callable[[str], str] | None = None,
    period_label: Callable[[str], str] | None = None,
) -> ReportResult:
    """Tickets opened inside the window, grouped by bucket x status.

    Each row is one ``(bucket_start, status_code, count)`` triple. The
    HTML view pivots this client-side via Jinja; the CSV ships the
    long format so spreadsheets can pivot however they like.
    """
    bucket = choose_bucket(window)
    rows_raw = (
        session.query(
            ServiceTicket.created_at,
            ServiceTicket.status,
        )
        .filter(
            ServiceTicket.created_at >= _to_naive_utc(window.start),
            ServiceTicket.created_at < _to_naive_utc(window.end_exclusive),
        )
        .all()
    )
    grouped: dict[tuple[date, str], int] = defaultdict(int)
    for created_at, status in rows_raw:
        key = (bucket_for(created_at.date(), bucket), str(status))
        grouped[key] += 1
    label_for_status = status_label or (lambda code: code)
    label_for_period = period_label or (lambda code: code)
    out_rows = sorted(
        (
            (d.isoformat(), code, label_for_status(code), count)
            for (d, code), count in grouped.items()
        ),
        key=lambda r: (r[0], r[1]),
    )
    headers = [label_for_period(bucket), "code", "label", "count"]
    total = sum(int(r[3]) for r in out_rows)
    return ReportResult(
        headers=headers,
        rows=[tuple(r) for r in out_rows],
        total_row=("", "", "TOTAL", total),
        bucket=bucket,
    )


# ── 2. interventions_by_machine ──────────────────────────────────────────────


def interventions_by_machine(
    session: Session,
    *,
    window: DateWindow,
) -> ReportResult:
    """Interventions started inside the window, grouped by equipment.

    Duration is the sum of ``(ended_at - started_at)`` minutes for
    closed interventions; still-open interventions add zero to the
    duration column and 1 to the count column.
    """
    rows_raw = (
        session.query(ServiceIntervention)
        .join(ServiceIntervention.ticket)
        .filter(
            ServiceIntervention.started_at >= _to_naive_utc(window.start),
            ServiceIntervention.started_at < _to_naive_utc(window.end_exclusive),
        )
        .all()
    )
    by_equipment: dict[bytes | None, dict[str, Any]] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "open": 0}
    )
    for iv in rows_raw:
        equipment_id = iv.ticket.equipment_id if iv.ticket is not None else None
        slot = by_equipment[equipment_id]
        slot["count"] = int(slot["count"]) + 1
        if iv.duration_minutes is not None:
            slot["minutes"] = int(slot["minutes"]) + int(iv.duration_minutes)
        else:
            slot["open"] = int(slot["open"]) + 1
    out_rows: list[tuple[Any, ...]] = []
    for equipment_id, agg in by_equipment.items():
        equipment = session.get(Equipment, equipment_id) if equipment_id is not None else None
        code = equipment_id.hex() if equipment_id is not None else ""
        label = equipment.label if equipment is not None else "—"
        out_rows.append(
            (
                code,
                label,
                int(agg["count"]),
                int(agg["minutes"]),
                int(agg["open"]),
            )
        )
    out_rows.sort(key=lambda r: int(r[2]), reverse=True)
    total = (
        "",
        "TOTAL",
        sum(int(r[2]) for r in out_rows),
        sum(int(r[3]) for r in out_rows),
        sum(int(r[4]) for r in out_rows),
    )
    headers = ["equipment_id", "label", "count", "minutes", "open"]
    return ReportResult(headers=headers, rows=out_rows, total_row=total)


# ── 3. parts_used ────────────────────────────────────────────────────────────


def parts_used(
    session: Session,
    *,
    window: DateWindow,
) -> ReportResult:
    """Quantity of each part consumed inside the window."""
    rows_raw = (
        session.query(
            ServicePartUsage.part_code,
            ServicePartUsage.description,
            func.sum(ServicePartUsage.quantity),
        )
        .join(
            ServiceIntervention,
            ServiceIntervention.id == ServicePartUsage.intervention_id,
        )
        .filter(
            ServiceIntervention.started_at >= _to_naive_utc(window.start),
            ServiceIntervention.started_at < _to_naive_utc(window.end_exclusive),
        )
        .group_by(ServicePartUsage.part_code, ServicePartUsage.description)
        .all()
    )
    out_rows: list[tuple[Any, ...]] = []
    for code, description, qty in rows_raw:
        master = session.query(PartMaster).filter(PartMaster.code == code).first()
        out_rows.append(
            (
                str(code),
                description or (master.description if master is not None else ""),
                int(qty or 0),
            )
        )
    out_rows.sort(key=lambda r: int(r[2]), reverse=True)
    total = ("", "TOTAL", sum(int(r[2]) for r in out_rows))
    headers = ["part_code", "description", "quantity"]
    return ReportResult(headers=headers, rows=out_rows, total_row=total)


# ── 4. maintenance_due_vs_completed ──────────────────────────────────────────


def maintenance_due_vs_completed(
    session: Session,
    *,
    window: DateWindow,
    period_label: Callable[[str], str] | None = None,
) -> ReportResult:
    """Maintenance throughput by period bucket.

    Due: ``MaintenanceTask.due_on`` inside the window.
    Completed: ``MaintenanceExecution.completed_at`` inside the window.
    """
    bucket = choose_bucket(window)
    due_rows = (
        session.query(MaintenanceTask.due_on)
        .filter(
            MaintenanceTask.due_on >= window.start,
            MaintenanceTask.due_on < window.end_exclusive,
        )
        .all()
    )
    completed_rows = (
        session.query(MaintenanceExecution.completed_at)
        .filter(
            MaintenanceExecution.completed_at >= _to_naive_utc(window.start),
            MaintenanceExecution.completed_at < _to_naive_utc(window.end_exclusive),
        )
        .all()
    )
    due_by_bucket: dict[date, int] = defaultdict(int)
    completed_by_bucket: dict[date, int] = defaultdict(int)
    for (due_on,) in due_rows:
        due_by_bucket[bucket_for(due_on, bucket)] += 1
    for (completed_at,) in completed_rows:
        completed_by_bucket[bucket_for(completed_at.date(), bucket)] += 1
    keys = sorted(set(due_by_bucket) | set(completed_by_bucket))
    out_rows: list[tuple[Any, ...]] = []
    for key in keys:
        due_count = due_by_bucket.get(key, 0)
        done_count = completed_by_bucket.get(key, 0)
        out_rows.append((key.isoformat(), int(due_count), int(done_count)))
    headers = [
        (period_label(bucket) if period_label else bucket),
        "due",
        "completed",
    ]
    total = (
        "TOTAL",
        sum(int(r[1]) for r in out_rows),
        sum(int(r[2]) for r in out_rows),
    )
    return ReportResult(headers=headers, rows=out_rows, total_row=total, bucket=bucket)


# ── 5. technician_workload ───────────────────────────────────────────────────


def technician_workload(
    session: Session,
    *,
    window: DateWindow,
) -> ReportResult:
    """Per-technician summary inside the window.

    Columns: interventions count, total minutes (closed only), open
    interventions, completed maintenance tasks.
    """
    techs = session.query(Technician).order_by(Technician.display_name).all()
    interventions = (
        session.query(ServiceIntervention)
        .filter(
            ServiceIntervention.started_at >= _to_naive_utc(window.start),
            ServiceIntervention.started_at < _to_naive_utc(window.end_exclusive),
        )
        .all()
    )
    by_user: dict[bytes, dict[str, int]] = defaultdict(
        lambda: {"count": 0, "minutes": 0, "open": 0}
    )
    for iv in interventions:
        if iv.technician_user_id is None:  # pragma: no cover - guard for legacy data
            continue
        slot = by_user[iv.technician_user_id]
        slot["count"] = slot["count"] + 1
        if iv.duration_minutes is not None:
            slot["minutes"] = slot["minutes"] + int(iv.duration_minutes)
        else:
            slot["open"] = slot["open"] + 1
    executions = (
        session.query(MaintenanceExecution)
        .join(MaintenanceTask, MaintenanceTask.id == MaintenanceExecution.task_id)
        .filter(
            MaintenanceExecution.completed_at >= _to_naive_utc(window.start),
            MaintenanceExecution.completed_at < _to_naive_utc(window.end_exclusive),
        )
        .all()
    )
    completed_by_tech: dict[bytes, int] = defaultdict(int)
    for ex in executions:
        tech_id = ex.task.assigned_technician_id
        if tech_id is not None:
            completed_by_tech[tech_id] = completed_by_tech[tech_id] + 1

    out_rows: list[tuple[Any, ...]] = []
    for tech in techs:
        agg = by_user.get(tech.user_id, {"count": 0, "minutes": 0, "open": 0})
        completed = completed_by_tech.get(tech.id, 0)
        out_rows.append(
            (
                tech.id.hex(),
                tech.label,
                int(agg["count"]),
                int(agg["minutes"]),
                int(agg["open"]),
                int(completed),
            )
        )
    # Catch unassigned-tech interventions (assignee user has no Technician row).
    tech_user_ids = {t.user_id for t in techs}
    for user_id, agg in by_user.items():
        if user_id in tech_user_ids:
            continue
        user = session.get(User, user_id)
        out_rows.append(
            (
                "",
                user.email if user is not None else "—",
                int(agg["count"]),
                int(agg["minutes"]),
                int(agg["open"]),
                0,
            )
        )
    out_rows.sort(key=lambda r: int(r[2]), reverse=True)
    total = (
        "",
        "TOTAL",
        sum(int(r[2]) for r in out_rows),
        sum(int(r[3]) for r in out_rows),
        sum(int(r[4]) for r in out_rows),
        sum(int(r[5]) for r in out_rows),
    )
    headers = ["technician_id", "label", "interventions", "minutes", "open", "maintenance_done"]
    return ReportResult(headers=headers, rows=out_rows, total_row=total)


# ── 6. repeat_issues ─────────────────────────────────────────────────────────


def repeat_issues(
    session: Session,
    *,
    window: DateWindow,
    min_tickets: int = 2,
) -> ReportResult:
    """Equipment with more than one ticket opened inside the window."""
    rows_raw = (
        session.query(
            ServiceTicket.equipment_id,
            func.count(ServiceTicket.id),
        )
        .filter(
            ServiceTicket.equipment_id.is_not(None),
            ServiceTicket.created_at >= _to_naive_utc(window.start),
            ServiceTicket.created_at < _to_naive_utc(window.end_exclusive),
        )
        .group_by(ServiceTicket.equipment_id)
        .having(func.count(ServiceTicket.id) >= min_tickets)
        .all()
    )
    out_rows: list[tuple[Any, ...]] = []
    for equipment_id, count in rows_raw:
        equipment = session.get(Equipment, equipment_id) if equipment_id is not None else None
        if equipment is None:  # pragma: no cover - FK is SET NULL; can't happen for filtered rows
            continue
        client = equipment.client
        out_rows.append(
            (
                equipment_id.hex(),
                equipment.label,
                client.name if client is not None else "—",
                int(count),
            )
        )
    out_rows.sort(key=lambda r: int(r[3]), reverse=True)
    headers = ["equipment_id", "label", "client", "tickets"]
    total = ("", "", "TOTAL", sum(int(r[3]) for r in out_rows))
    return ReportResult(headers=headers, rows=out_rows, total_row=total)


# ── Lookup ───────────────────────────────────────────────────────────────────


def planning_summary_for_links(
    *,
    plan: MaintenancePlan | None,
) -> str:
    """Free-floating helper used by templates when rendering plan links."""
    if plan is None:  # pragma: no cover - guard only
        return ""
    return plan.template.name if plan.template is not None else ""


__all__ = [
    "PERIOD_DAY",
    "PERIOD_MONTH",
    "PERIOD_WEEK",
    "ReportResult",
    "bucket_for",
    "choose_bucket",
    "interventions_by_machine",
    "maintenance_due_vs_completed",
    "parts_used",
    "planning_summary_for_links",
    "repeat_issues",
    "technician_workload",
    "tickets_by_status",
]
