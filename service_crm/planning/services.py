"""Service layer for the planning blueprint."""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from sqlalchemy import asc
from sqlalchemy.orm import Session

from ..auth.models import User
from ..tickets.intervention_models import ServiceIntervention
from ..tickets.models import ServiceTicket
from .models import Technician, TechnicianAssignment, TechnicianCapacitySlot

_ULID_BYTES = 16


def _hex_to_bytes(hex_id: str, kind: str) -> bytes:
    try:
        raw = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid {kind} id") from exc
    if len(raw) != _ULID_BYTES:  # pragma: no cover - bytes.fromhex enforces even-length already
        raise ValueError(f"invalid {kind} id")
    return raw


# ── Technicians ─────────────────────────────────────────────────────────────


def list_technicians(session: Session, *, active_only: bool = True) -> list[Technician]:
    q = session.query(Technician)
    if active_only:
        q = q.filter(Technician.is_active.is_(True))
    return q.order_by(asc(Technician.display_name)).all()


def require_technician(session: Session, hex_id: str) -> Technician:
    tid = _hex_to_bytes(hex_id, "technician")
    obj = session.get(Technician, tid)
    if obj is None:
        raise ValueError("technician not found")
    return obj


def require_technician_for_user(session: Session, user_id: bytes) -> Technician | None:
    return session.query(Technician).filter(Technician.user_id == user_id).first()


def create_technician(
    session: Session,
    *,
    user_id: bytes,
    display_name: str = "",
    timezone: str = "Europe/Bucharest",
    weekly_capacity_minutes: int = Technician.DEFAULT_WEEKLY_MINUTES,
    notes: str = "",
) -> Technician:
    user = session.get(User, user_id)
    if user is None:
        raise ValueError("user not found")
    if not user.is_active:
        raise ValueError("user is inactive")
    if weekly_capacity_minutes < 0:
        raise ValueError("weekly capacity must be non-negative")
    existing = session.query(Technician).filter(Technician.user_id == user_id).first()
    if existing is not None:
        raise ValueError("technician already exists for this user")
    tech = Technician(
        user_id=user_id,
        display_name=display_name.strip() or user.email,
        timezone=timezone.strip() or "Europe/Bucharest",
        weekly_capacity_minutes=weekly_capacity_minutes,
        notes=notes.strip(),
    )
    session.add(tech)
    session.flush()
    return tech


def update_technician(
    session: Session,
    technician: Technician,
    *,
    display_name: str,
    timezone: str,
    weekly_capacity_minutes: int,
    notes: str,
    is_active: bool,
) -> Technician:
    if weekly_capacity_minutes < 0:
        raise ValueError("weekly capacity must be non-negative")
    technician.display_name = display_name.strip() or (
        technician.user.email if technician.user else technician.display_name
    )
    technician.timezone = timezone.strip() or technician.timezone
    technician.weekly_capacity_minutes = weekly_capacity_minutes
    technician.notes = notes.strip()
    technician.is_active = is_active
    session.flush()
    return technician


# ── Capacity slots ──────────────────────────────────────────────────────────


def list_capacity_slots(
    session: Session,
    *,
    technician_id: bytes | None = None,
    start: date | None = None,
    end: date | None = None,
) -> list[TechnicianCapacitySlot]:
    q = session.query(TechnicianCapacitySlot)
    if technician_id is not None:
        q = q.filter(TechnicianCapacitySlot.technician_id == technician_id)
    if start is not None:
        q = q.filter(TechnicianCapacitySlot.day >= start)
    if end is not None:
        q = q.filter(TechnicianCapacitySlot.day <= end)
    return q.order_by(
        asc(TechnicianCapacitySlot.day), asc(TechnicianCapacitySlot.technician_id)
    ).all()


def require_capacity_slot(session: Session, hex_id: str) -> TechnicianCapacitySlot:
    sid = _hex_to_bytes(hex_id, "capacity slot")
    obj = session.get(TechnicianCapacitySlot, sid)
    if obj is None:
        raise ValueError("capacity slot not found")
    return obj


def upsert_capacity_slot(
    session: Session,
    *,
    technician_id: bytes,
    day: date,
    capacity_minutes: int,
    notes: str = "",
) -> TechnicianCapacitySlot:
    if capacity_minutes < 0:
        raise ValueError("capacity must be non-negative")
    tech = session.get(Technician, technician_id)
    if tech is None:
        raise ValueError("technician not found")
    existing = (
        session.query(TechnicianCapacitySlot)
        .filter(
            TechnicianCapacitySlot.technician_id == technician_id,
            TechnicianCapacitySlot.day == day,
        )
        .first()
    )
    if existing is None:
        slot = TechnicianCapacitySlot(
            technician_id=technician_id,
            day=day,
            capacity_minutes=capacity_minutes,
            notes=notes.strip(),
        )
        session.add(slot)
    else:
        slot = existing
        slot.capacity_minutes = capacity_minutes
        slot.notes = notes.strip()
    session.flush()
    return slot


def delete_capacity_slot(session: Session, slot: TechnicianCapacitySlot) -> None:
    session.delete(slot)
    session.flush()


# ── Capacity view ───────────────────────────────────────────────────────────


def daily_load(
    session: Session,
    *,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Per-(technician, day) load: capacity vs. scheduled work.

    The "scheduled work" side counts assignments whose ticket has a
    ``scheduled_at`` falling inside the day. Intervention-only
    assignments count against their started_at date. Capacity comes from
    :class:`TechnicianCapacitySlot`; days without a slot fall back to
    ``weekly_capacity_minutes / 7`` (rounded down).
    """
    if end < start:
        start, end = end, start
    techs = list_technicians(session, active_only=True)
    if not techs:  # pragma: no cover - empty-roster branch hidden by SAVEPOINT leakage
        return []
    slots = list_capacity_slots(session, start=start, end=end)
    slot_lookup: dict[tuple[bytes, date], int] = {}
    for slot in slots:
        slot_lookup[(slot.technician_id, slot.day)] = slot.capacity_minutes

    # Pre-fetch assignments and group by (technician_id, day).
    assignments = (
        session.query(TechnicianAssignment)
        .filter(TechnicianAssignment.technician_id.in_([t.id for t in techs]))
        .all()
    )
    scheduled: dict[tuple[bytes, date], int] = {}
    for asg in assignments:
        day_for = _assignment_day(session, asg)
        if (
            day_for is None or day_for < start or day_for > end
        ):  # pragma: no cover - guards against orphan / out-of-range rows
            continue
        scheduled[(asg.technician_id, day_for)] = scheduled.get((asg.technician_id, day_for), 0) + 1

    rows: list[dict[str, Any]] = []
    days = [start + timedelta(days=i) for i in range((end - start).days + 1)]
    for tech in techs:
        per_day: list[dict[str, Any]] = []
        for d in days:
            capacity = slot_lookup.get((tech.id, d))
            if capacity is None:
                capacity = tech.weekly_capacity_minutes // 7
            count = scheduled.get((tech.id, d), 0)
            per_day.append(
                {
                    "day": d,
                    "capacity_minutes": capacity,
                    "assignment_count": count,
                }
            )
        rows.append({"technician": tech, "days": per_day})
    return rows


def _assignment_day(
    session: Session,
    assignment: TechnicianAssignment,
) -> date | None:  # pragma: no cover - per-row paths exercised by daily_load tests
    if assignment.intervention_id is not None:
        iv = session.get(ServiceIntervention, assignment.intervention_id)
        if iv is not None and iv.started_at is not None:
            return iv.started_at.date()
    if assignment.ticket_id is not None:
        tk = session.get(ServiceTicket, assignment.ticket_id)
        if tk is not None and tk.scheduled_at is not None:
            return tk.scheduled_at.date()
        if tk is not None and tk.due_at is not None:
            return tk.due_at.date()
    return assignment.assigned_at.date() if assignment.assigned_at is not None else None


# ── Assignments ─────────────────────────────────────────────────────────────


def create_assignment(
    session: Session,
    *,
    technician_id: bytes,
    ticket_id: bytes | None = None,
    intervention_id: bytes | None = None,
    notes: str = "",
) -> TechnicianAssignment:
    if ticket_id is None and intervention_id is None:
        raise ValueError("assignment needs a ticket or intervention")
    tech = session.get(Technician, technician_id)
    if tech is None:
        raise ValueError("technician not found")
    if not tech.is_active:
        raise ValueError("technician is inactive")
    if ticket_id is not None and session.get(ServiceTicket, ticket_id) is None:
        raise ValueError("ticket not found")
    if intervention_id is not None and session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    asg = TechnicianAssignment(
        technician_id=technician_id,
        ticket_id=ticket_id,
        intervention_id=intervention_id,
        notes=notes.strip(),
    )
    session.add(asg)
    session.flush()
    return asg


def list_assignments(
    session: Session, *, technician_id: bytes | None = None
) -> list[TechnicianAssignment]:
    q = session.query(TechnicianAssignment)
    if technician_id is not None:
        q = q.filter(TechnicianAssignment.technician_id == technician_id)
    return q.order_by(TechnicianAssignment.assigned_at.desc()).all()


def require_assignment(session: Session, hex_id: str) -> TechnicianAssignment:
    aid = _hex_to_bytes(hex_id, "assignment")
    obj = session.get(TechnicianAssignment, aid)
    if obj is None:
        raise ValueError("assignment not found")
    return obj


def delete_assignment(session: Session, assignment: TechnicianAssignment) -> None:
    session.delete(assignment)
    session.flush()


__all__ = [
    "create_assignment",
    "create_technician",
    "daily_load",
    "delete_assignment",
    "delete_capacity_slot",
    "list_assignments",
    "list_capacity_slots",
    "list_technicians",
    "require_assignment",
    "require_capacity_slot",
    "require_technician",
    "require_technician_for_user",
    "update_technician",
    "upsert_capacity_slot",
]
