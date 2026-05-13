"""Service layer for the intervention / parts half of the tickets blueprint.

Mirrors the conventions in :mod:`.services`:

- All SQL lives here.
- Cross-blueprint access goes through the other blueprint's
  ``services.py``.
- Soft-deletes via ``is_active`` where the model has the column;
  intervention rows are hard-deletable because the audit chain is in
  ``audit_event`` and a typo-d intervention has no FK chain to break.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any, BinaryIO

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from ..auth.models import User
from ..extensions import db
from ..shared import clock, uploads
from .intervention_models import (
    InterventionAction,
    InterventionFinding,
    PartMaster,
    ServiceIntervention,
    ServicePartUsage,
)
from .models import ServiceTicket, TicketAttachment

# ── Helpers ──────────────────────────────────────────────────────────────────


def _aware(dt: datetime) -> datetime:
    """Force a naive datetime to UTC so comparisons cross dialects.

    SQLite returns naive datetimes from ``DateTime(timezone=True)``
    columns even when an aware value was written; we don't want a
    spurious comparison failure on a developer laptop.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt


def _dialect() -> str:
    return db.engine.dialect.name


_ULID_BYTES = 16


def _hex_to_bytes(hex_id: str, kind: str) -> bytes:
    try:
        raw = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid {kind} id") from exc
    if len(raw) != _ULID_BYTES:
        raise ValueError(f"invalid {kind} id")
    return raw


# ── Interventions ────────────────────────────────────────────────────────────


def require_intervention(session: Session, hex_id: str) -> ServiceIntervention:
    iid = _hex_to_bytes(hex_id, "intervention")
    obj = session.get(ServiceIntervention, iid)
    if obj is None:
        raise ValueError("intervention not found")
    return obj


def list_for_ticket(session: Session, ticket_id: bytes) -> list[ServiceIntervention]:
    return (
        session.query(ServiceIntervention)
        .filter(ServiceIntervention.ticket_id == ticket_id)
        .order_by(desc(ServiceIntervention.started_at))
        .all()
    )


def create_intervention(
    session: Session,
    *,
    ticket_id: bytes,
    technician_user_id: bytes | None,
    started_at: datetime | None = None,
    summary: str = "",
) -> ServiceIntervention:
    if session.get(ServiceTicket, ticket_id) is None:
        raise ValueError("ticket not found")
    if technician_user_id is not None:
        tech = session.get(User, technician_user_id)
        if tech is None:
            raise ValueError("technician not found")
        if not tech.is_active:
            raise ValueError("technician is inactive")
    intervention = ServiceIntervention(
        ticket_id=ticket_id,
        technician_user_id=technician_user_id,
        started_at=started_at or clock.now(),
        summary=summary.strip(),
    )
    session.add(intervention)
    session.flush()
    return intervention


def update_intervention(
    session: Session,
    intervention: ServiceIntervention,
    *,
    technician_user_id: bytes | None,
    started_at: datetime,
    ended_at: datetime | None,
    summary: str,
) -> ServiceIntervention:
    if ended_at is not None and _aware(ended_at) < _aware(started_at):
        raise ValueError("ended_at must be at or after started_at")
    if technician_user_id is not None:
        tech = session.get(User, technician_user_id)
        if tech is None:
            raise ValueError("technician not found")
        if not tech.is_active:
            raise ValueError("technician is inactive")
    intervention.technician_user_id = technician_user_id
    intervention.started_at = started_at
    intervention.ended_at = ended_at
    intervention.summary = summary.strip()
    session.flush()
    return intervention


def stop_intervention(
    session: Session,
    intervention: ServiceIntervention,
    *,
    ended_at: datetime | None = None,
) -> ServiceIntervention:
    when = ended_at or clock.now()
    if _aware(when) < _aware(intervention.started_at):
        raise ValueError("ended_at must be at or after started_at")
    intervention.ended_at = when
    session.flush()
    return intervention


def delete_intervention(session: Session, intervention: ServiceIntervention) -> None:
    session.delete(intervention)
    session.flush()


# ── Actions ──────────────────────────────────────────────────────────────────


def add_action(
    session: Session,
    *,
    intervention_id: bytes,
    description: str,
    duration_minutes: int | None = None,
) -> InterventionAction:
    description = description.strip()
    if not description:
        raise ValueError("description is required")
    if len(description.encode("utf-8")) > InterventionAction.DESCRIPTION_MAX_BYTES:
        raise ValueError(
            f"description exceeds {InterventionAction.DESCRIPTION_MAX_BYTES // 1024} KB"
        )
    if duration_minutes is not None and duration_minutes < 0:
        raise ValueError("duration must be non-negative")
    if session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    action = InterventionAction(
        intervention_id=intervention_id,
        description=description,
        duration_minutes=duration_minutes,
    )
    session.add(action)
    session.flush()
    return action


def require_action(session: Session, hex_id: str) -> InterventionAction:
    aid = _hex_to_bytes(hex_id, "action")
    obj = session.get(InterventionAction, aid)
    if obj is None:
        raise ValueError("action not found")
    return obj


def delete_action(session: Session, action: InterventionAction) -> None:
    session.delete(action)
    session.flush()


# ── Findings ─────────────────────────────────────────────────────────────────


def add_finding(
    session: Session,
    *,
    intervention_id: bytes,
    description: str,
    is_root_cause: bool = False,
) -> InterventionFinding:
    description = description.strip()
    if not description:
        raise ValueError("description is required")
    if len(description.encode("utf-8")) > InterventionFinding.DESCRIPTION_MAX_BYTES:
        raise ValueError(
            f"description exceeds {InterventionFinding.DESCRIPTION_MAX_BYTES // 1024} KB"
        )
    if session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    finding = InterventionFinding(
        intervention_id=intervention_id,
        description=description,
        is_root_cause=is_root_cause,
    )
    session.add(finding)
    session.flush()
    return finding


def require_finding(session: Session, hex_id: str) -> InterventionFinding:
    fid = _hex_to_bytes(hex_id, "finding")
    obj = session.get(InterventionFinding, fid)
    if obj is None:
        raise ValueError("finding not found")
    return obj


def delete_finding(session: Session, finding: InterventionFinding) -> None:
    session.delete(finding)
    session.flush()


# ── Part master ──────────────────────────────────────────────────────────────


def _part_search_filter(q: str) -> Any:
    q = q.strip()
    if not q:
        return None
    if _dialect() == "postgresql":
        from sqlalchemy import literal_column

        tsq = func.plainto_tsquery(literal_column("'simple'"), q)
        text = func.coalesce(PartMaster.code, "") + " " + func.coalesce(PartMaster.description, "")
        return func.to_tsvector(literal_column("'simple'"), text).op("@@")(tsq)
    pattern = f"%{q.lower()}%"
    return or_(
        func.lower(PartMaster.code).like(pattern),
        func.lower(PartMaster.description).like(pattern),
    )


def list_parts(
    session: Session,
    *,
    q: str = "",
    active_only: bool = True,
) -> list[PartMaster]:
    base = session.query(PartMaster)
    if active_only:
        base = base.filter(PartMaster.is_active.is_(True))
    flt = _part_search_filter(q)
    if flt is not None:
        base = base.filter(flt)
    return base.order_by(asc(PartMaster.code)).all()


def require_part(session: Session, hex_id: str) -> PartMaster:
    pid = _hex_to_bytes(hex_id, "part")
    obj = session.get(PartMaster, pid)
    if obj is None:
        raise ValueError("part not found")
    return obj


def create_part(
    session: Session,
    *,
    code: str,
    description: str = "",
    unit: str = "pcs",
    notes: str = "",
) -> PartMaster:
    code = code.strip()
    if not code:
        raise ValueError("part code is required")
    existing = session.query(PartMaster).filter(func.lower(PartMaster.code) == code.lower()).first()
    if existing is not None:
        raise ValueError("part code already exists")
    part = PartMaster(
        code=code,
        description=description.strip(),
        unit=unit.strip() or "pcs",
        notes=notes.strip(),
    )
    session.add(part)
    session.flush()
    return part


def update_part(
    session: Session,
    part: PartMaster,
    *,
    description: str,
    unit: str,
    notes: str,
    is_active: bool,
) -> PartMaster:
    part.description = description.strip()
    part.unit = unit.strip() or "pcs"
    part.notes = notes.strip()
    part.is_active = is_active
    session.flush()
    return part


# ── Part usage ───────────────────────────────────────────────────────────────


def add_part_usage(
    session: Session,
    *,
    intervention_id: bytes,
    part_id: bytes | None,
    part_code: str = "",
    description: str = "",
    quantity: int = 1,
    unit: str = "pcs",
) -> ServicePartUsage:
    if quantity <= 0:
        raise ValueError("quantity must be positive")
    if session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    resolved_code = part_code.strip()
    resolved_description = description.strip()
    resolved_unit = (unit or "pcs").strip() or "pcs"
    if part_id is not None:
        part = session.get(PartMaster, part_id)
        if part is None:
            raise ValueError("part not found")
        # Snapshot the catalog values when the caller didn't override.
        if not resolved_code:
            resolved_code = part.code
        if not resolved_description:
            resolved_description = part.description
        if unit == "pcs":  # caller didn't choose a unit
            resolved_unit = part.unit or "pcs"
    if not resolved_code:
        raise ValueError("part code is required")
    usage = ServicePartUsage(
        intervention_id=intervention_id,
        part_id=part_id,
        part_code=resolved_code,
        description=resolved_description,
        quantity=quantity,
        unit=resolved_unit,
    )
    session.add(usage)
    session.flush()
    return usage


def require_part_usage(session: Session, hex_id: str) -> ServicePartUsage:
    pid = _hex_to_bytes(hex_id, "part usage")
    obj = session.get(ServicePartUsage, pid)
    if obj is None:
        raise ValueError("part usage not found")
    return obj


def delete_part_usage(session: Session, usage: ServicePartUsage) -> None:
    session.delete(usage)
    session.flush()


def coalesce_parts(
    usages: list[ServicePartUsage],
) -> list[tuple[str, str, int, str]]:
    """Group raw usage rows by ``part_code``; return one tuple per part.

    Used by the detail template — keeps rendering logic out of Jinja.
    """
    grouped: dict[str, dict[str, Any]] = {}
    for u in usages:
        entry = grouped.setdefault(
            u.part_code,
            {"description": u.description, "quantity": 0, "unit": u.unit},
        )
        entry["quantity"] += int(u.quantity)
    return [
        (code, data["description"], int(data["quantity"]), data["unit"])
        for code, data in grouped.items()
    ]


# ── Photo upload (reuses shared/uploads.py) ──────────────────────────────────


def add_intervention_photo(
    session: Session,
    *,
    intervention: ServiceIntervention,
    uploader_user_id: bytes | None,
    stream: BinaryIO,
    filename: str,
    declared_content_type: str = "",
) -> TicketAttachment:
    """Photo uploaded against an intervention is stored as a
    :class:`TicketAttachment` with ``intervention_id`` set."""
    stored = uploads.store_upload(
        stream=stream,
        original_filename=filename,
        declared_content_type=declared_content_type,
        scope="interventions",
        owner_id=intervention.id,
    )
    attachment = TicketAttachment(
        ticket_id=intervention.ticket_id,
        intervention_id=intervention.id,
        uploader_user_id=uploader_user_id,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        storage_key=stored.storage_key,
    )
    session.add(attachment)
    session.flush()
    return attachment


def list_intervention_photos(session: Session, intervention_id: bytes) -> list[TicketAttachment]:
    return (
        session.query(TicketAttachment)
        .filter(
            TicketAttachment.intervention_id == intervention_id,
            TicketAttachment.is_active.is_(True),
        )
        .order_by(desc(TicketAttachment.created_at))
        .all()
    )


__all__ = [
    "add_action",
    "add_finding",
    "add_intervention_photo",
    "add_part_usage",
    "coalesce_parts",
    "create_intervention",
    "create_part",
    "delete_action",
    "delete_finding",
    "delete_intervention",
    "delete_part_usage",
    "list_for_ticket",
    "list_intervention_photos",
    "list_parts",
    "require_action",
    "require_finding",
    "require_intervention",
    "require_part",
    "require_part_usage",
    "stop_intervention",
    "update_intervention",
    "update_part",
]
