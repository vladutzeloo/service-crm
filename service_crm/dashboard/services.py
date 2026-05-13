"""Aggregation services for the dashboard blueprint.

Every function takes an explicit :class:`Session` and returns plain
Python data (lists of dicts / dataclasses), never an ORM object that
the template can wander off and lazy-load. This is the seam the
0.9 perf-budget validation will sit behind — if any tile blows the
300 ms P95 target on the reference dataset, the fix lands in this
module without touching routes or templates.

No writes. No commits. No model mutations.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from ..clients.models import Client
from ..equipment.models import Equipment
from ..maintenance.models import MaintenancePlan, MaintenanceTask, TaskStatus
from ..planning.models import Technician, TechnicianAssignment
from ..planning.services import DEFAULT_ASSIGNMENT_MINUTES
from ..shared import clock
from ..shared.date_window import DateWindow, this_week
from ..tickets.intervention_models import ServiceIntervention
from ..tickets.models import ServiceTicket
from ..tickets.state import TicketStatus

# Equipment with at least this many tickets opened inside the window
# is flagged "high-risk" on the manager dashboard. Tunable; lives here
# rather than as a magic literal scattered across the template.
HIGH_RISK_MIN_TICKETS = 3

# Cap on the "recent interventions" panel. 10 rows matches the
# precedent set by the maintenance task list.
RECENT_INTERVENTIONS_LIMIT = 10

# Cap on the "upcoming maintenance" panel. 10 rows, ordered by the
# nearest ``next_due_on``.
UPCOMING_MAINTENANCE_LIMIT = 10

# Cap on the technician's own queue items. The phone view stays usable
# even when a tech has a long backlog.
MY_QUEUE_LIMIT = 25

# Saturation thresholds for the technician load tone. Mirrors the
# planning capacity grid (see ``planning/services.py``).
_LOAD_TONE_SUCCESS = 0.75
_LOAD_TONE_WARNING = 1.0

# Open status set = anything that isn't terminal. Match
# ``tickets/services.list_tickets(open_only=True)``.
_OPEN_STATUSES = tuple(
    s.value for s in TicketStatus if s not in (TicketStatus.CLOSED, TicketStatus.CANCELLED)
)


@dataclass(frozen=True)
class Kpi:
    """A single dashboard tile.

    ``value`` is the primary number formatted at render time (so
    locale-aware number formatting stays in the template). ``help_text``
    is an optional second line. ``drill_endpoint`` + ``drill_kwargs``
    drive the click-through into a filtered list — every tile is
    drillable per the ROADMAP §0.8 ease-of-use bar.
    """

    code: str
    value: int | str
    help_text: str = ""
    drill_endpoint: str | None = None
    drill_kwargs: dict[str, Any] | None = None


# ── Manager view ─────────────────────────────────────────────────────────────


def manager_kpis(session: Session, *, today: date | None = None) -> list[Kpi]:
    """The six primary tiles for the manager dashboard."""
    today = today or clock.now().date()
    week = this_week(today=today)

    active_clients = (
        session.query(func.count(Client.id)).filter(Client.is_active.is_(True)).scalar() or 0
    )
    open_tickets = (
        session.query(func.count(ServiceTicket.id))
        .filter(ServiceTicket.status.in_(_OPEN_STATUSES))
        .scalar()
        or 0
    )
    now_dt = clock.now()
    overdue_tickets = (
        session.query(func.count(ServiceTicket.id))
        .filter(
            ServiceTicket.status.in_(_OPEN_STATUSES),
            ServiceTicket.due_at.is_not(None),
            ServiceTicket.due_at < now_dt,
        )
        .scalar()
        or 0
    )
    due_maintenance = (
        session.query(func.count(MaintenancePlan.id))
        .filter(
            MaintenancePlan.is_active.is_(True),
            MaintenancePlan.next_due_on.is_not(None),
            MaintenancePlan.next_due_on >= week.start,
            MaintenancePlan.next_due_on < week.end_exclusive,
        )
        .scalar()
        or 0
    )
    waiting_parts = (
        session.query(func.count(ServiceTicket.id))
        .filter(ServiceTicket.status == TicketStatus.WAITING_PARTS.value)
        .scalar()
        or 0
    )
    utilization_pct = technician_utilization_pct(session, today=today)

    return [
        Kpi(
            code="active_clients",
            value=int(active_clients),
            drill_endpoint="clients.list_clients",
        ),
        Kpi(
            code="open_tickets",
            value=int(open_tickets),
            drill_endpoint="tickets.list_tickets",
            drill_kwargs={"open": "1"},
        ),
        Kpi(
            code="overdue_tickets",
            value=int(overdue_tickets),
            drill_endpoint="tickets.list_tickets",
            drill_kwargs={"open": "1", "overdue": "1"},
        ),
        Kpi(
            code="due_maintenance_week",
            value=int(due_maintenance),
            drill_endpoint="maintenance.plans_list",
            drill_kwargs={"overdue": "1"},
        ),
        Kpi(
            code="tickets_waiting_parts",
            value=int(waiting_parts),
            drill_endpoint="tickets.list_tickets",
            drill_kwargs={"status": TicketStatus.WAITING_PARTS.value},
        ),
        Kpi(
            code="technician_utilization",
            value=f"{utilization_pct}%",
            drill_endpoint="planning.capacity",
        ),
    ]


def technician_utilization_pct(session: Session, *, today: date | None = None) -> int:
    """Aggregate utilization across the current week.

    Numerator: assignments x ``DEFAULT_ASSIGNMENT_MINUTES`` (matches the
    capacity grid's weighting). Denominator: sum of weekly capacity
    minutes across active technicians. Returns an integer percentage,
    capped at 999 so a runaway value never wrecks the layout.
    """
    today = today or clock.now().date()
    week = this_week(today=today)

    techs = (
        session.query(Technician.id, Technician.weekly_capacity_minutes)
        .filter(Technician.is_active.is_(True))
        .all()
    )
    if not techs:
        return 0
    total_capacity = sum(int(weekly) for _, weekly in techs)
    if total_capacity <= 0:
        return 0
    tech_ids = [tid for tid, _ in techs]

    # Count assignments belonging to active techs and falling inside the
    # week. ``TechnicianAssignment.assigned_at`` is the simplest proxy —
    # finer-grained scheduling lands with v1.3 capacity slots.
    assignment_count = (
        session.query(func.count(TechnicianAssignment.id))
        .filter(
            TechnicianAssignment.technician_id.in_(tech_ids),
            TechnicianAssignment.assigned_at >= _to_naive_utc(week.start),
            TechnicianAssignment.assigned_at < _to_naive_utc(week.end_exclusive),
        )
        .scalar()
        or 0
    )
    scheduled_minutes = int(assignment_count) * DEFAULT_ASSIGNMENT_MINUTES
    pct = round(100 * scheduled_minutes / total_capacity)
    return min(pct, 999)


def _to_naive_utc(d: date) -> datetime:
    """``date`` → midnight UTC ``datetime``.

    ``ServiceTicket.due_at`` and friends are timezone-aware columns;
    SQLAlchemy + SQLite accept a naive datetime for the comparison
    fine, but Postgres-side we want explicit UTC so the index is hit.
    """
    return datetime(d.year, d.month, d.day)


# ── Secondary panels ─────────────────────────────────────────────────────────


def tickets_by_status(session: Session) -> list[tuple[str, int]]:
    """Same data as :func:`tickets.services.status_counts`, ordered by
    the canonical lifecycle so panel rows render in the order managers
    expect."""
    rows: dict[str, int] = dict(
        session.query(ServiceTicket.status, func.count(ServiceTicket.id))
        .group_by(ServiceTicket.status)
        .all()
    )
    order = [s.value for s in TicketStatus]
    return [(code, int(rows.get(code, 0))) for code in order if rows.get(code, 0)]


def upcoming_maintenance(
    session: Session,
    *,
    limit: int = UPCOMING_MAINTENANCE_LIMIT,
) -> list[MaintenancePlan]:
    """Active plans with the nearest ``next_due_on`` in ascending order."""
    return (
        session.query(MaintenancePlan)
        .filter(
            MaintenancePlan.is_active.is_(True),
            MaintenancePlan.next_due_on.is_not(None),
        )
        .order_by(MaintenancePlan.next_due_on.asc())
        .limit(limit)
        .all()
    )


def recent_interventions(
    session: Session,
    *,
    limit: int = RECENT_INTERVENTIONS_LIMIT,
) -> list[ServiceIntervention]:
    """Most-recently started interventions across all technicians."""
    return (
        session.query(ServiceIntervention)
        .order_by(ServiceIntervention.started_at.desc())
        .limit(limit)
        .all()
    )


def high_risk_machines(
    session: Session,
    *,
    window: DateWindow,
    min_tickets: int = HIGH_RISK_MIN_TICKETS,
) -> list[dict[str, Any]]:
    """Equipment with ≥ ``min_tickets`` opened inside ``window``.

    The dashboard's "recurring issues" proxy until v1.3 lands the
    proper ``TechnicianSkill`` + finding-bucketing report. Returns
    plain dicts so the template doesn't lazy-load the equipment
    relationship.
    """
    rows = (
        session.query(
            ServiceTicket.equipment_id,
            func.count(ServiceTicket.id).label("ticket_count"),
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
    out: list[dict[str, Any]] = []
    for equipment_id, count in rows:
        equipment = session.get(Equipment, equipment_id) if equipment_id is not None else None
        if equipment is None:  # pragma: no cover - orphan guard (FK is SET NULL)
            continue
        out.append(
            {
                "equipment": equipment,
                "ticket_count": int(count),
            }
        )
    out.sort(key=lambda row: int(row["ticket_count"]), reverse=True)
    return out


def technician_load_week(
    session: Session,
    *,
    today: date | None = None,
) -> list[dict[str, Any]]:
    """Per-technician summary for the current week.

    Counts assignments and converts to minutes using the same constant
    the planning capacity grid uses, so the two views agree.
    """
    today = today or clock.now().date()
    week = this_week(today=today)
    techs = (
        session.query(Technician)
        .filter(Technician.is_active.is_(True))
        .order_by(Technician.display_name)
        .all()
    )
    if not techs:
        return []
    counts_by_tech: dict[bytes, int] = dict(
        session.query(
            TechnicianAssignment.technician_id,
            func.count(TechnicianAssignment.id),
        )
        .filter(
            TechnicianAssignment.technician_id.in_([t.id for t in techs]),
            TechnicianAssignment.assigned_at >= _to_naive_utc(week.start),
            TechnicianAssignment.assigned_at < _to_naive_utc(week.end_exclusive),
        )
        .group_by(TechnicianAssignment.technician_id)
        .all()
    )
    rows: list[dict[str, Any]] = []
    for tech in techs:
        count = int(counts_by_tech.get(tech.id, 0))
        scheduled = count * DEFAULT_ASSIGNMENT_MINUTES
        capacity = int(tech.weekly_capacity_minutes)
        ratio = (scheduled / capacity) if capacity else 0.0
        if ratio < _LOAD_TONE_SUCCESS:
            tone = "success"
        elif ratio < _LOAD_TONE_WARNING:
            tone = "warning"
        else:
            tone = "danger"
        rows.append(
            {
                "technician": tech,
                "assignment_count": count,
                "scheduled_minutes": scheduled,
                "capacity_minutes": capacity,
                "tone": tone,
            }
        )
    return rows


# ── Technician view ──────────────────────────────────────────────────────────


def my_open_tickets(
    session: Session,
    *,
    user_id: bytes,
    limit: int = MY_QUEUE_LIMIT,
) -> list[ServiceTicket]:
    """Non-terminal tickets where I'm the assignee, newest first."""
    return (
        session.query(ServiceTicket)
        .filter(
            ServiceTicket.assignee_user_id == user_id,
            ServiceTicket.status.in_(_OPEN_STATUSES),
        )
        .order_by(ServiceTicket.created_at.desc())
        .limit(limit)
        .all()
    )


def my_overdue_tickets(
    session: Session,
    *,
    user_id: bytes,
) -> list[ServiceTicket]:
    """Non-terminal tickets where I'm the assignee and ``due_at`` is in
    the past."""
    now_dt = clock.now()
    return (
        session.query(ServiceTicket)
        .filter(
            ServiceTicket.assignee_user_id == user_id,
            ServiceTicket.status.in_(_OPEN_STATUSES),
            ServiceTicket.due_at.is_not(None),
            ServiceTicket.due_at < now_dt,
        )
        .order_by(ServiceTicket.due_at.asc())
        .all()
    )


def my_maintenance_tasks(
    session: Session,
    *,
    technician_id: bytes | None,
    limit: int = MY_QUEUE_LIMIT,
) -> list[MaintenanceTask]:
    """Pending maintenance tasks assigned to my Technician row."""
    if technician_id is None:
        return []
    return (
        session.query(MaintenanceTask)
        .filter(
            MaintenanceTask.assigned_technician_id == technician_id,
            MaintenanceTask.status == TaskStatus.PENDING,
        )
        .order_by(MaintenanceTask.due_on.asc())
        .limit(limit)
        .all()
    )


def technician_summary(
    session: Session,
    *,
    user_id: bytes,
    technician_id: bytes | None,
    today: date | None = None,
) -> dict[str, int]:
    """Counts powering the technician dashboard's small KPI strip."""
    today = today or clock.now().date()
    now_dt = clock.now()
    open_count = (
        session.query(func.count(ServiceTicket.id))
        .filter(
            ServiceTicket.assignee_user_id == user_id,
            ServiceTicket.status.in_(_OPEN_STATUSES),
        )
        .scalar()
        or 0
    )
    overdue_count = (
        session.query(func.count(ServiceTicket.id))
        .filter(
            ServiceTicket.assignee_user_id == user_id,
            ServiceTicket.status.in_(_OPEN_STATUSES),
            ServiceTicket.due_at.is_not(None),
            ServiceTicket.due_at < now_dt,
        )
        .scalar()
        or 0
    )
    tasks_count = 0
    if technician_id is not None:
        tasks_count = (
            session.query(func.count(MaintenanceTask.id))
            .filter(
                MaintenanceTask.assigned_technician_id == technician_id,
                MaintenanceTask.status == TaskStatus.PENDING,
            )
            .scalar()
            or 0
        )
    overdue_tasks_count = 0
    if technician_id is not None:
        overdue_tasks_count = (
            session.query(func.count(MaintenanceTask.id))
            .filter(
                MaintenanceTask.assigned_technician_id == technician_id,
                MaintenanceTask.status == TaskStatus.PENDING,
                MaintenanceTask.due_on < today,
            )
            .scalar()
            or 0
        )
    return {
        "open_tickets": int(open_count),
        "overdue_tickets": int(overdue_count),
        "pending_tasks": int(tasks_count),
        "overdue_tasks": int(overdue_tasks_count),
    }


# ── Helpers ──────────────────────────────────────────────────────────────────


def default_window(*, today: date | None = None) -> DateWindow:
    """Rolling 30-day window the manager dashboard uses for panels
    that don't have an obvious "this week" framing."""
    today = today or clock.now().date()
    return DateWindow(start=today - timedelta(days=29), end_exclusive=today + timedelta(days=1))


__all__ = [
    "HIGH_RISK_MIN_TICKETS",
    "MY_QUEUE_LIMIT",
    "RECENT_INTERVENTIONS_LIMIT",
    "UPCOMING_MAINTENANCE_LIMIT",
    "Kpi",
    "default_window",
    "high_risk_machines",
    "manager_kpis",
    "my_maintenance_tasks",
    "my_open_tickets",
    "my_overdue_tickets",
    "recent_interventions",
    "technician_load_week",
    "technician_summary",
    "technician_utilization_pct",
    "tickets_by_status",
    "upcoming_maintenance",
]
