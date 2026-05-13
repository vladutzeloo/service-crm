"""Service layer for the maintenance blueprint.

Owns every query that touches the four maintenance tables. The
``next_due_on`` computation (template + plan + scheduler) lives here so
no route ever writes the column directly.

The plan-state rule from
[`docs/v0.7-plan.md`](../../docs/v0.7-plan.md) §2.3 — one open task per
plan — is enforced by :func:`generate_pending_tasks` and tested in
``tests/maintenance/test_services.py``.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import asc, func
from sqlalchemy.orm import Session

from ..equipment.models import Equipment
from ..knowledge.models import ChecklistTemplate
from ..shared import clock
from ..tickets.intervention_models import ServiceIntervention
from ..tickets.models import ServiceTicket, TicketPriority, TicketType
from ..tickets.services import create_ticket
from .models import (
    MaintenanceExecution,
    MaintenancePlan,
    MaintenanceTask,
    MaintenanceTemplate,
    TaskStatus,
)

_ULID_BYTES = 16


def _hex_to_bytes(hex_id: str, kind: str) -> bytes:
    try:
        raw = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid {kind} id") from exc
    if len(raw) != _ULID_BYTES:  # pragma: no cover - bytes.fromhex enforces even-length already
        raise ValueError(f"invalid {kind} id")
    return raw


def _today() -> date:
    return clock.now().date()


# ── Templates ────────────────────────────────────────────────────────────────


def list_templates(session: Session, *, active_only: bool = True) -> list[MaintenanceTemplate]:
    q = session.query(MaintenanceTemplate)
    if active_only:
        q = q.filter(MaintenanceTemplate.is_active.is_(True))
    return q.order_by(asc(MaintenanceTemplate.name)).all()


def require_template(session: Session, hex_id: str) -> MaintenanceTemplate:
    tid = _hex_to_bytes(hex_id, "maintenance template")
    obj = session.get(MaintenanceTemplate, tid)
    if obj is None:
        raise ValueError("template not found")
    return obj


def create_template(
    session: Session,
    *,
    name: str,
    description: str = "",
    cadence_days: int = 180,
    estimated_minutes: int | None = None,
    checklist_template_id: bytes | None = None,
) -> MaintenanceTemplate:
    name = name.strip()
    if not name:
        raise ValueError("template name is required")
    if cadence_days <= 0:
        raise ValueError("cadence must be a positive number of days")
    if estimated_minutes is not None and estimated_minutes < 0:
        raise ValueError("estimated minutes must be non-negative")
    if checklist_template_id is not None and (
        session.get(ChecklistTemplate, checklist_template_id) is None
    ):
        raise ValueError("checklist template not found")
    existing = (
        session.query(MaintenanceTemplate)
        .filter(func.lower(MaintenanceTemplate.name) == name.lower())
        .first()
    )
    if existing is not None:
        raise ValueError("template name already exists")
    tpl = MaintenanceTemplate(
        name=name,
        description=description.strip(),
        cadence_days=cadence_days,
        estimated_minutes=estimated_minutes,
        checklist_template_id=checklist_template_id,
    )
    session.add(tpl)
    session.flush()
    return tpl


def update_template(
    session: Session,
    template: MaintenanceTemplate,
    *,
    name: str,
    description: str,
    cadence_days: int,
    estimated_minutes: int | None,
    checklist_template_id: bytes | None,
    is_active: bool,
) -> MaintenanceTemplate:
    name = name.strip()
    if not name:
        raise ValueError("template name is required")
    if cadence_days <= 0:
        raise ValueError("cadence must be a positive number of days")
    if estimated_minutes is not None and estimated_minutes < 0:
        raise ValueError("estimated minutes must be non-negative")
    if checklist_template_id is not None and (
        session.get(ChecklistTemplate, checklist_template_id) is None
    ):
        raise ValueError("checklist template not found")
    if name.lower() != template.name.lower():
        clash = (
            session.query(MaintenanceTemplate)
            .filter(func.lower(MaintenanceTemplate.name) == name.lower())
            .first()
        )
        if clash is not None and clash.id != template.id:
            raise ValueError("template name already exists")
    template.name = name
    template.description = description.strip()
    template.cadence_days = cadence_days
    template.estimated_minutes = estimated_minutes
    template.checklist_template_id = checklist_template_id
    template.is_active = is_active
    session.flush()
    return template


# ── Plans ────────────────────────────────────────────────────────────────────


def list_plans(
    session: Session,
    *,
    equipment_id: bytes | None = None,
    active_only: bool = True,
    overdue_only: bool = False,
) -> list[MaintenancePlan]:
    q = session.query(MaintenancePlan)
    if active_only:
        q = q.filter(MaintenancePlan.is_active.is_(True))
    if equipment_id is not None:
        q = q.filter(MaintenancePlan.equipment_id == equipment_id)
    if overdue_only:
        today = _today()
        q = q.filter(MaintenancePlan.next_due_on.is_not(None)).filter(
            MaintenancePlan.next_due_on < today
        )
    return q.order_by(asc(MaintenancePlan.next_due_on)).all()


def require_plan(session: Session, hex_id: str) -> MaintenancePlan:
    pid = _hex_to_bytes(hex_id, "maintenance plan")
    obj = session.get(MaintenancePlan, pid)
    if obj is None:
        raise ValueError("plan not found")
    return obj


def create_plan(
    session: Session,
    *,
    equipment_id: bytes,
    template_id: bytes,
    cadence_days: int | None = None,
    last_done_on: date | None = None,
    notes: str = "",
) -> MaintenancePlan:
    equipment = session.get(Equipment, equipment_id)
    if equipment is None:
        raise ValueError("equipment not found")
    if not equipment.is_active:
        raise ValueError("equipment is inactive")
    template = session.get(MaintenanceTemplate, template_id)
    if template is None:
        raise ValueError("template not found")
    if not template.is_active:
        raise ValueError("template is inactive")
    effective_cadence = cadence_days if cadence_days is not None else template.cadence_days
    if effective_cadence <= 0:
        raise ValueError("cadence must be a positive number of days")
    plan = MaintenancePlan(
        equipment_id=equipment_id,
        template_id=template_id,
        cadence_days=effective_cadence,
        last_done_on=last_done_on,
        notes=notes.strip(),
    )
    session.add(plan)
    session.flush()
    _recompute_plan(plan)
    session.flush()
    return plan


def update_plan(
    session: Session,
    plan: MaintenancePlan,
    *,
    cadence_days: int,
    last_done_on: date | None,
    notes: str,
    is_active: bool,
) -> MaintenancePlan:
    if cadence_days <= 0:
        raise ValueError("cadence must be a positive number of days")
    plan.cadence_days = cadence_days
    plan.last_done_on = last_done_on
    plan.notes = notes.strip()
    plan.is_active = is_active
    _recompute_plan(plan)
    session.flush()
    return plan


def _recompute_plan(plan: MaintenancePlan) -> None:
    """Set ``plan.next_due_on`` from ``last_done_on`` + ``cadence_days``.

    If the plan has never been executed, the seed is the plan's
    ``created_at`` (its creation date); the resulting due date is
    ``created_at + cadence_days``.
    """
    if not plan.is_active:
        plan.next_due_on = None
        return
    base: date
    if plan.last_done_on is not None:
        base = plan.last_done_on
    elif plan.created_at is not None:
        base = plan.created_at.date()
    else:  # pragma: no cover - SQLAlchemy default fires at flush
        base = _today()
    plan.next_due_on = base + timedelta(days=plan.cadence_days)


def recompute_plan(session: Session, plan: MaintenancePlan) -> MaintenancePlan:
    """Public wrapper around :func:`_recompute_plan` for route / scheduler use."""
    _recompute_plan(plan)
    session.flush()
    return plan


# ── Tasks ────────────────────────────────────────────────────────────────────


def list_tasks(
    session: Session,
    *,
    status: str | None = None,
    plan_id: bytes | None = None,
    overdue_only: bool = False,
    technician_id: bytes | None = None,
) -> list[MaintenanceTask]:
    q = session.query(MaintenanceTask)
    if status is not None:
        if status not in TaskStatus.ALL:
            raise ValueError(f"unknown status {status!r}")
        q = q.filter(MaintenanceTask.status == status)
    if plan_id is not None:
        q = q.filter(MaintenanceTask.plan_id == plan_id)
    if technician_id is not None:
        q = q.filter(MaintenanceTask.assigned_technician_id == technician_id)
    if overdue_only:
        today = _today()
        q = q.filter(
            MaintenanceTask.status == TaskStatus.PENDING,
            MaintenanceTask.due_on < today,
        )
    return q.order_by(asc(MaintenanceTask.due_on)).all()


def require_task(session: Session, hex_id: str) -> MaintenanceTask:
    tid = _hex_to_bytes(hex_id, "maintenance task")
    obj = session.get(MaintenanceTask, tid)
    if obj is None:
        raise ValueError("task not found")
    return obj


def assign_task(
    session: Session,
    task: MaintenanceTask,
    *,
    technician_id: bytes | None,
) -> MaintenanceTask:
    if task.status != TaskStatus.PENDING:
        raise ValueError("cannot reassign a task that is not pending")
    if technician_id is not None:
        # Lazy import to avoid a planning↔maintenance cycle at module load.
        from ..planning.models import Technician

        tech = session.get(Technician, technician_id)
        if tech is None:
            raise ValueError("technician not found")
        if not tech.is_active:
            raise ValueError("technician is inactive")
    task.assigned_technician_id = technician_id
    session.flush()
    return task


def generate_pending_tasks(
    session: Session,
    *,
    plan: MaintenancePlan | None = None,
    horizon_days: int = 14,
) -> list[MaintenanceTask]:
    """Generate one ``pending`` task per active plan whose ``next_due_on``
    falls inside ``horizon_days`` and which currently has no open task.

    Returns the freshly created task rows. If ``plan`` is provided only
    that plan is considered.
    """
    today = _today()
    horizon = today + timedelta(days=horizon_days)
    base = session.query(MaintenancePlan).filter(MaintenancePlan.is_active.is_(True))
    if plan is not None:
        base = base.filter(MaintenancePlan.id == plan.id)
    candidates = base.all()
    created: list[MaintenanceTask] = []
    for p in candidates:
        if p.next_due_on is None or p.next_due_on > horizon:
            continue
        open_task = _open_task_for(session, p.id)
        if open_task is not None:
            continue
        task = MaintenanceTask(
            plan_id=p.id,
            due_on=p.next_due_on,
            status=TaskStatus.PENDING,
        )
        session.add(task)
        created.append(task)
    if created:
        session.flush()
    return created


def _open_task_for(session: Session, plan_id: bytes) -> MaintenanceTask | None:
    return (
        session.query(MaintenanceTask)
        .filter(
            MaintenanceTask.plan_id == plan_id,
            MaintenanceTask.status == TaskStatus.PENDING,
        )
        .order_by(MaintenanceTask.due_on)
        .first()
    )


def complete_task(
    session: Session,
    task: MaintenanceTask,
    *,
    intervention_id: bytes | None = None,
    notes: str = "",
    completed_at: datetime | None = None,
) -> MaintenanceExecution:
    """Record a completion against ``task``.

    Side effects, all inside the caller's transaction:

    - Adds a :class:`MaintenanceExecution` row.
    - Flips ``task.status`` to ``done``.
    - Bumps ``plan.last_done_on`` and recomputes ``plan.next_due_on``.
    - Generates the next pending task if the plan is still in the
      horizon.
    """
    if task.status != TaskStatus.PENDING:
        raise ValueError("task is not pending")
    if intervention_id is not None and session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    when = completed_at or clock.now()
    execution = MaintenanceExecution(
        task_id=task.id,
        intervention_id=intervention_id,
        completed_at=when,
        notes=notes.strip(),
    )
    session.add(execution)
    task.status = TaskStatus.DONE
    plan = task.plan
    plan.last_done_on = when.date()
    _recompute_plan(plan)
    session.flush()
    # The horizon-bound generator picks up the bumped next_due_on so a
    # short cadence (e.g. 1 day) immediately materialises the follow-up.
    generate_pending_tasks(session, plan=plan)
    return execution


def escalate_task(
    session: Session,
    task: MaintenanceTask,
    *,
    title: str = "",
    description: str = "",
) -> ServiceTicket:
    """Open a :class:`ServiceTicket` from ``task``.

    The ticket is pre-populated from the plan + template; the caller
    can override ``title`` and ``description``. ``task.ticket_id`` is
    set so the link is bidirectional. The task flips to
    ``escalated``.
    """
    if task.status != TaskStatus.PENDING:
        raise ValueError("task is not pending")
    plan = task.plan
    equipment = plan.equipment
    template = plan.template
    seed_title = title.strip() or f"{template.name} — {equipment.label}"
    seed_description = description.strip() or template.description
    type_id = _lookup_code_id(session, TicketType, "preventive")
    priority_id = _lookup_code_id(session, TicketPriority, "normal")
    ticket = create_ticket(
        session,
        client_id=equipment.client_id,
        title=seed_title,
        description=seed_description,
        equipment_id=equipment.id,
        type_id=type_id,
        priority_id=priority_id,
    )
    task.status = TaskStatus.ESCALATED
    task.ticket_id = ticket.id
    session.flush()
    return ticket


def _lookup_code_id(session: Session, model: Any, code: str) -> bytes | None:
    row = session.query(model).filter(func.lower(model.code) == code.lower()).first()
    return bytes(row.id) if row is not None else None


# ── Scheduler entrypoint ─────────────────────────────────────────────────────


def scheduler_tick(session: Session, *, horizon_days: int = 14) -> dict[str, int]:
    """Recompute every active plan's ``next_due_on`` and generate any
    pending task whose due date falls inside ``horizon_days``.

    Idempotent — calling it twice produces no extra rows. Returns a
    small stats dict so the caller / CLI can flash a result.
    """
    plans = session.query(MaintenancePlan).filter(MaintenancePlan.is_active.is_(True)).all()
    for plan in plans:
        _recompute_plan(plan)
    session.flush()
    created = generate_pending_tasks(session, horizon_days=horizon_days)
    return {"plans_recomputed": len(plans), "tasks_generated": len(created)}


__all__ = [
    "assign_task",
    "complete_task",
    "create_plan",
    "create_template",
    "escalate_task",
    "generate_pending_tasks",
    "list_plans",
    "list_tasks",
    "list_templates",
    "recompute_plan",
    "require_plan",
    "require_task",
    "require_template",
    "scheduler_tick",
    "update_plan",
    "update_template",
]
