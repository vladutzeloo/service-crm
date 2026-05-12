"""Service layer for the tickets blueprint.

All SQL lives here. The state machine in :mod:`.state` is consulted by
:func:`transition_ticket` to check the requested move; the
``before_flush`` listener in :mod:`service_crm.shared.audit` writes the
corresponding :class:`TicketStatusHistory` row inside the same flush.

Search is dialect-aware: Postgres uses a GIN expression-index on
``title || description``; SQLite falls back to LIKE.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any, BinaryIO

from sqlalchemy import asc, desc, func, or_
from sqlalchemy.orm import Session

from ..auth.models import User
from ..clients.models import Client
from ..equipment.models import Equipment
from ..extensions import db
from ..shared import clock, uploads
from .models import (
    ServiceTicket,
    TicketAttachment,
    TicketComment,
    TicketPriority,
    TicketStatusHistory,
    TicketType,
)
from .state import IllegalTransition, TicketStatus, transition

# ── Helpers ──────────────────────────────────────────────────────────────────


def _dialect() -> str:
    return db.engine.dialect.name


def _ticket_search_filter(q: str) -> Any:
    q = q.strip()
    if not q:
        return None

    if _dialect() == "postgresql":
        from sqlalchemy import literal_column

        tsq = func.plainto_tsquery(literal_column("'simple'"), q)
        text = (
            func.coalesce(ServiceTicket.title, "")
            + " "
            + func.coalesce(ServiceTicket.description, "")
        )
        return func.to_tsvector(literal_column("'simple'"), text).op("@@")(tsq)

    pattern = f"%{q.lower()}%"
    return or_(
        func.lower(ServiceTicket.title).like(pattern),
        func.lower(ServiceTicket.description).like(pattern),
    )


def _next_ticket_number(session: Session) -> int:
    """Return the next monotonic ticket number.

    On Postgres uses the ``ticket_number_seq`` sequence (race-free across
    concurrent writers). On SQLite, scans ``MAX(number)+1`` inside the
    current transaction — the test fixture's ``BEGIN IMMEDIATE`` semantics
    serialise concurrent writers via the RESERVED lock, so the read-then-
    write is atomic from any single process's perspective.
    """
    if _dialect() == "postgresql":
        from sqlalchemy import text

        # The sequence is created lazily; create on first use so the
        # migration stays simple and SQLite doesn't see it at all.
        session.execute(text("CREATE SEQUENCE IF NOT EXISTS ticket_number_seq START 1"))
        result = session.execute(text("SELECT nextval('ticket_number_seq')")).scalar_one()
        return int(result)

    last = session.query(func.coalesce(func.max(ServiceTicket.number), 0)).scalar()
    return int(last or 0) + 1


# ── Lookups: ticket types ────────────────────────────────────────────────────


def list_ticket_types(session: Session, *, active_only: bool = True) -> list[TicketType]:
    q = session.query(TicketType)
    if active_only:
        q = q.filter(TicketType.is_active.is_(True))
    return q.order_by(TicketType.label).all()


def require_ticket_type(session: Session, hex_id: str) -> TicketType:
    try:
        tid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid ticket type id") from exc
    obj = session.get(TicketType, tid)
    if obj is None:
        raise ValueError("ticket type not found")
    return obj


def default_ticket_type(session: Session) -> TicketType | None:
    return (
        session.query(TicketType)
        .filter(TicketType.is_active.is_(True), TicketType.is_default.is_(True))
        .first()
    )


def update_ticket_type(
    session: Session,
    obj: TicketType,
    *,
    label: str,
    is_active: bool,
) -> TicketType:
    obj.label = label.strip()
    obj.is_active = is_active
    session.flush()
    return obj


# ── Lookups: ticket priorities ───────────────────────────────────────────────


def list_ticket_priorities(
    session: Session, *, active_only: bool = True
) -> list[TicketPriority]:
    q = session.query(TicketPriority)
    if active_only:
        q = q.filter(TicketPriority.is_active.is_(True))
    return q.order_by(TicketPriority.rank).all()


def require_ticket_priority(session: Session, hex_id: str) -> TicketPriority:
    try:
        pid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid ticket priority id") from exc
    obj = session.get(TicketPriority, pid)
    if obj is None:
        raise ValueError("ticket priority not found")
    return obj


def default_ticket_priority(session: Session) -> TicketPriority | None:
    return (
        session.query(TicketPriority)
        .filter(TicketPriority.is_active.is_(True), TicketPriority.is_default.is_(True))
        .first()
    )


def update_ticket_priority(
    session: Session,
    obj: TicketPriority,
    *,
    label: str,
    is_active: bool,
) -> TicketPriority:
    obj.label = label.strip()
    obj.is_active = is_active
    session.flush()
    return obj


# ── Equipment-belongs-to-client guard ────────────────────────────────────────


def _validate_equipment_belongs_to_client(
    session: Session, *, client_id: bytes, equipment_id: bytes | None
) -> None:
    if equipment_id is None:
        return
    eq = session.get(Equipment, equipment_id)
    if eq is None:
        raise ValueError("equipment not found")
    if eq.client_id != client_id:
        raise ValueError("equipment does not belong to this client")


def _validate_user_active(session: Session, user_id: bytes | None) -> None:
    if user_id is None:
        return
    u = session.get(User, user_id)
    if u is None:
        raise ValueError("assignee not found")
    if not u.is_active:
        raise ValueError("assignee is inactive")


# ── Tickets ──────────────────────────────────────────────────────────────────


def require_ticket(session: Session, hex_id: str) -> ServiceTicket:
    try:
        tid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid ticket id") from exc
    obj = session.get(ServiceTicket, tid)
    if obj is None:
        raise ValueError("ticket not found")
    return obj


def create_ticket(
    session: Session,
    *,
    client_id: bytes,
    title: str,
    description: str = "",
    equipment_id: bytes | None = None,
    type_id: bytes | None = None,
    priority_id: bytes | None = None,
    assignee_user_id: bytes | None = None,
    due_at: datetime | None = None,
    sla_due_at: datetime | None = None,
) -> ServiceTicket:
    if session.get(Client, client_id) is None:
        raise ValueError("client not found")
    _validate_equipment_belongs_to_client(
        session, client_id=client_id, equipment_id=equipment_id
    )
    _validate_user_active(session, assignee_user_id)
    if not title.strip():
        raise ValueError("title is required")
    if type_id is not None and session.get(TicketType, type_id) is None:
        raise ValueError("ticket type not found")
    if priority_id is not None and session.get(TicketPriority, priority_id) is None:
        raise ValueError("ticket priority not found")

    number = _next_ticket_number(session)
    ticket = ServiceTicket(
        number=number,
        client_id=client_id,
        equipment_id=equipment_id,
        type_id=type_id,
        priority_id=priority_id,
        assignee_user_id=assignee_user_id,
        title=title.strip(),
        description=description.strip(),
        status=TicketStatus.NEW.value,
        due_at=due_at,
        sla_due_at=sla_due_at,
    )
    session.add(ticket)
    session.flush()
    return ticket


def update_ticket(
    session: Session,
    ticket: ServiceTicket,
    *,
    title: str,
    description: str,
    equipment_id: bytes | None,
    type_id: bytes | None,
    priority_id: bytes | None,
    assignee_user_id: bytes | None,
    due_at: datetime | None,
    sla_due_at: datetime | None,
) -> ServiceTicket:
    if not title.strip():
        raise ValueError("title is required")
    _validate_equipment_belongs_to_client(
        session, client_id=ticket.client_id, equipment_id=equipment_id
    )
    _validate_user_active(session, assignee_user_id)
    if type_id is not None and session.get(TicketType, type_id) is None:
        raise ValueError("ticket type not found")
    if priority_id is not None and session.get(TicketPriority, priority_id) is None:
        raise ValueError("ticket priority not found")
    ticket.title = title.strip()
    ticket.description = description.strip()
    ticket.equipment_id = equipment_id
    ticket.type_id = type_id
    ticket.priority_id = priority_id
    ticket.assignee_user_id = assignee_user_id
    ticket.due_at = due_at
    ticket.sla_due_at = sla_due_at
    session.flush()
    return ticket


def transition_ticket(
    session: Session,
    ticket: ServiceTicket,
    *,
    to_state: TicketStatus,
    role: str,
    reason: str = "",
    reason_code: str = "",
) -> ServiceTicket:
    """Move ``ticket`` to ``to_state``.

    Validates the move through :func:`state.transition`; raises
    :class:`IllegalTransition` if rejected. The accompanying
    :class:`TicketStatusHistory` row is written by the ``before_flush``
    listener — :func:`stash_transition_meta` attaches the reason metadata
    so the listener picks it up.
    """
    current = ticket.status_enum
    transition(current, to_state, role)
    if to_state is TicketStatus.CANCELLED and not reason.strip():
        raise ValueError("a reason is required for cancellation")
    _stash_transition_meta(ticket, reason=reason, reason_code=reason_code)
    ticket.status = to_state.value
    if to_state is TicketStatus.CLOSED:
        ticket.closed_at = clock.now()
    session.flush()
    return ticket


def _stash_transition_meta(
    ticket: ServiceTicket, *, reason: str, reason_code: str
) -> None:
    """Attach a one-shot ``{reason, reason_code}`` dict to the instance.

    The audit listener reads it when building the history row and clears
    it afterwards, so the metadata is per-transition rather than
    persistent.
    """
    ticket._pending_history_meta = {
        "reason": reason,
        "reason_code": reason_code,
    }


def list_tickets(
    session: Session,
    *,
    q: str = "",
    statuses: list[str] | None = None,
    type_id: bytes | None = None,
    priority_id: bytes | None = None,
    client_id: bytes | None = None,
    equipment_id: bytes | None = None,
    assignee_user_id: bytes | None = None,
    open_only: bool = False,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[ServiceTicket], int]:
    base = session.query(ServiceTicket)
    if statuses:
        base = base.filter(ServiceTicket.status.in_(statuses))
    if open_only:
        base = base.filter(
            ServiceTicket.status.notin_(
                [TicketStatus.CLOSED.value, TicketStatus.CANCELLED.value]
            )
        )
    if type_id is not None:
        base = base.filter(ServiceTicket.type_id == type_id)
    if priority_id is not None:
        base = base.filter(ServiceTicket.priority_id == priority_id)
    if client_id is not None:
        base = base.filter(ServiceTicket.client_id == client_id)
    if equipment_id is not None:
        base = base.filter(ServiceTicket.equipment_id == equipment_id)
    if assignee_user_id is not None:
        base = base.filter(ServiceTicket.assignee_user_id == assignee_user_id)
    flt = _ticket_search_filter(q)
    if flt is not None:
        base = base.filter(flt)
    total: int = base.count()
    items: list[ServiceTicket] = (
        base.order_by(desc(ServiceTicket.created_at), asc(ServiceTicket.number))
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def list_for_equipment(session: Session, equipment_id: bytes) -> list[ServiceTicket]:
    return (
        session.query(ServiceTicket)
        .filter(ServiceTicket.equipment_id == equipment_id)
        .order_by(desc(ServiceTicket.created_at))
        .all()
    )


def list_for_client(session: Session, client_id: bytes) -> list[ServiceTicket]:
    return (
        session.query(ServiceTicket)
        .filter(ServiceTicket.client_id == client_id)
        .order_by(desc(ServiceTicket.created_at))
        .all()
    )


def status_counts(session: Session) -> dict[str, int]:
    """Group ticket count by status, used for filter-chip badges."""
    rows = (
        session.query(ServiceTicket.status, func.count(ServiceTicket.id))
        .group_by(ServiceTicket.status)
        .all()
    )
    return {str(status): int(count) for status, count in rows}


# ── Comments ─────────────────────────────────────────────────────────────────


def add_comment(
    session: Session,
    *,
    ticket_id: bytes,
    author_user_id: bytes | None,
    body: str,
) -> TicketComment:
    body = body.strip()
    if not body:
        raise ValueError("comment body is required")
    if len(body.encode("utf-8")) > TicketComment.BODY_MAX_BYTES:
        raise ValueError(
            f"comment exceeds {TicketComment.BODY_MAX_BYTES // 1024} KB"
        )
    if session.get(ServiceTicket, ticket_id) is None:
        raise ValueError("ticket not found")
    comment = TicketComment(
        ticket_id=ticket_id,
        author_user_id=author_user_id,
        body=body,
    )
    session.add(comment)
    session.flush()
    return comment


def list_comments(session: Session, ticket_id: bytes) -> list[TicketComment]:
    return (
        session.query(TicketComment)
        .filter(TicketComment.ticket_id == ticket_id, TicketComment.is_active.is_(True))
        .order_by(TicketComment.created_at)
        .all()
    )


def soft_delete_comment(session: Session, comment: TicketComment) -> None:
    comment.is_active = False
    session.flush()


# ── Attachments ──────────────────────────────────────────────────────────────


def require_attachment(
    session: Session, hex_id: str, ticket: ServiceTicket
) -> TicketAttachment:
    try:
        aid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid attachment id") from exc
    obj = session.get(TicketAttachment, aid)
    if obj is None or obj.ticket_id != ticket.id:
        raise ValueError("attachment not found")
    return obj


def add_attachment(
    session: Session,
    *,
    ticket: ServiceTicket,
    uploader_user_id: bytes | None,
    stream: BinaryIO,
    filename: str,
    declared_content_type: str = "",
) -> TicketAttachment:
    stored = uploads.store_upload(
        stream=stream,
        original_filename=filename,
        declared_content_type=declared_content_type,
        scope="tickets",
        owner_id=ticket.id,
    )
    attachment = TicketAttachment(
        ticket_id=ticket.id,
        uploader_user_id=uploader_user_id,
        filename=stored.filename,
        content_type=stored.content_type,
        size_bytes=stored.size_bytes,
        storage_key=stored.storage_key,
    )
    session.add(attachment)
    session.flush()
    return attachment


def soft_delete_attachment(
    session: Session, attachment: TicketAttachment, *, reason: str
) -> None:
    if not reason.strip():
        raise ValueError("a reason is required to delete an attachment")
    attachment.is_active = False
    session.flush()


def list_attachments(session: Session, ticket_id: bytes) -> list[TicketAttachment]:
    return (
        session.query(TicketAttachment)
        .filter(
            TicketAttachment.ticket_id == ticket_id,
            TicketAttachment.is_active.is_(True),
        )
        .order_by(desc(TicketAttachment.created_at))
        .all()
    )


def list_history(session: Session, ticket_id: bytes) -> list[TicketStatusHistory]:
    return (
        session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket_id)
        .order_by(TicketStatusHistory.occurred_at)
        .all()
    )


__all__ = [
    "IllegalTransition",
    "add_attachment",
    "add_comment",
    "create_ticket",
    "default_ticket_priority",
    "default_ticket_type",
    "list_attachments",
    "list_comments",
    "list_for_client",
    "list_for_equipment",
    "list_history",
    "list_ticket_priorities",
    "list_ticket_types",
    "list_tickets",
    "require_attachment",
    "require_ticket",
    "require_ticket_priority",
    "require_ticket_type",
    "soft_delete_attachment",
    "soft_delete_comment",
    "status_counts",
    "transition_ticket",
    "update_ticket",
    "update_ticket_priority",
    "update_ticket_type",
]
