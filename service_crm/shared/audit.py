"""Audit log infrastructure.

Two pieces:

1. :class:`Auditable` — a mixin that gives a model ``created_at`` and
   ``updated_at`` columns. Cheap to add to every business model.
2. :class:`AuditEvent` — append-only log of create/update/delete events
   for any ``Auditable`` instance, captured by a ``before_flush`` hook.

The acting user and request id come from a :class:`contextvars.ContextVar`
that the auth blueprint will set on each request once it lands. Until
then the ``actor_user_id`` column is nullable.

Why ``before_flush`` instead of the per-row ``after_insert``/
``after_update``/``after_delete`` events suggested in the architecture
plan: ``before_flush`` runs once per transaction, sees the full set of
pending changes, and lets us write the audit row inside the same
transaction. Per-row events are awkward to use with the same session
and were the source of the rolled-back-audit-orphan class of bugs in
the prior planning round.
"""

from __future__ import annotations

import contextvars
from datetime import datetime
from typing import Any

from flask import current_app, has_app_context
from sqlalchemy import JSON, DateTime, Enum, String, event, inspect
from sqlalchemy.orm import Mapped, Session, mapped_column
from sqlalchemy.orm.base import NO_VALUE

from ..extensions import db
from . import clock, ulid

ACTOR_CTX: contextvars.ContextVar[bytes | None] = contextvars.ContextVar(
    "audit_actor_user_id", default=None
)
REQUEST_ID_CTX: contextvars.ContextVar[str | None] = contextvars.ContextVar(
    "audit_request_id", default=None
)


class Auditable:
    """Mixin: every model that needs an audit trail inherits from this."""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=clock.now, nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=clock.now,
        onupdate=clock.now,
        nullable=False,
    )


class AuditEvent(db.Model):  # type: ignore[name-defined,misc]
    __tablename__ = "audit_event"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    ts: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=clock.now, nullable=False, index=True
    )
    action: Mapped[str] = mapped_column(
        Enum("create", "update", "delete", name="audit_action"),
        nullable=False,
    )
    entity_type: Mapped[str] = mapped_column(String(80), nullable=False, index=True)
    entity_id: Mapped[bytes | None] = mapped_column(ulid.ULID, nullable=True)
    actor_user_id: Mapped[bytes | None] = mapped_column(ulid.ULID, nullable=True)
    request_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    before: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    after: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)


@event.listens_for(Session, "before_flush")
def _record_audit_events(session: Session, _flush_ctx: Any, _instances: Any) -> None:  # noqa: PLR0912

    if not _audit_enabled():
        return

    actor = ACTOR_CTX.get()
    request_id = REQUEST_ID_CTX.get()

    # Python-side ``default=ulid.new`` hasn't fired yet at before_flush, so
    # ``instance.id`` would still be ``None`` for new rows and the audit
    # event would lose its link back to the entity. Eagerly populate.
    # The mixin doesn't declare ``id`` itself (each subclass owns its PK),
    # so we set it dynamically.
    for instance in session.new:
        if (
            isinstance(instance, Auditable)
            and not isinstance(instance, AuditEvent)
            and getattr(instance, "id", None) is None
        ):
            instance.id = ulid.new()  # type: ignore[attr-defined]

    pending: list[AuditEvent] = []
    history_rows: list[Any] = []

    for instance in session.new:
        if isinstance(instance, Auditable) and not isinstance(instance, AuditEvent):
            pending.append(_event_for(instance, "create", actor, request_id))
            row = _ticket_creation_history(instance, actor)
            if row is not None:
                history_rows.append(row)
    for instance in session.dirty:
        if (
            isinstance(instance, Auditable)
            and not isinstance(instance, AuditEvent)
            and session.is_modified(instance, include_collections=False)
        ):
            pending.append(_event_for(instance, "update", actor, request_id))
            row = _ticket_status_change_history(instance, actor)
            if row is not None:
                history_rows.append(row)
    for instance in session.deleted:
        if isinstance(instance, Auditable) and not isinstance(instance, AuditEvent):
            pending.append(_event_for(instance, "delete", actor, request_id))

    for evt in pending:
        session.add(evt)
    for row in history_rows:
        session.add(row)


def _ticket_creation_history(instance: Any, actor: bytes | None) -> Any:
    """Build the initial ``from_state=NULL`` history row for a new ticket."""
    # Lazy import so the listener module stays loadable before the tickets
    # blueprint exists (e.g. during partial Alembic upgrades).
    try:
        from ..tickets.models import ServiceTicket, TicketStatusHistory
    except ImportError:  # pragma: no cover - tickets always imported in prod
        return None
    if not isinstance(instance, ServiceTicket):
        return None
    return TicketStatusHistory(
        ticket_id=instance.id,
        from_state=None,
        to_state=instance.status,
        actor_user_id=actor,
        occurred_at=clock.now(),
    )


def _ticket_status_change_history(instance: Any, actor: bytes | None) -> Any:
    """Build a history row when ``ServiceTicket.status`` changed in this flush."""
    try:
        from ..tickets.models import ServiceTicket, TicketStatusHistory
    except ImportError:  # pragma: no cover
        return None
    if not isinstance(instance, ServiceTicket):
        return None
    state: Any = inspect(instance)
    history = state.attrs.status.history
    if not history.deleted or not history.added:
        return None
    old_value = history.deleted[0]
    new_value = history.added[0]
    if old_value == new_value:  # pragma: no cover - SQLAlchemy never marks unchanged rows dirty
        return None
    reason = ""
    reason_code = ""
    pending = getattr(instance, "_pending_history_meta", None)
    if isinstance(pending, dict):
        reason = str(pending.get("reason", "") or "")
        reason_code = str(pending.get("reason_code", "") or "")
        instance._pending_history_meta = None
    return TicketStatusHistory(
        ticket_id=instance.id,
        from_state=str(old_value) if old_value is not None else None,
        to_state=str(new_value),
        actor_user_id=actor,
        reason=reason,
        reason_code=reason_code,
        occurred_at=clock.now(),
    )


def _audit_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("AUDIT_LOG_ENABLED", True))


_SKIP_KEYS = frozenset({"created_at", "updated_at"})


def _event_for(
    instance: Any,
    action: str,
    actor: bytes | None,
    request_id: str | None,
) -> AuditEvent:
    state = inspect(instance)

    before: dict[str, Any] | None = None
    after: dict[str, Any] | None = None

    if action == "create":
        after = _snapshot_after(state)
    elif action == "update":
        before, after = _snapshot_update(state)
    else:  # delete
        before = _snapshot_after(state)

    return AuditEvent(
        action=action,
        entity_type=type(instance).__name__,
        entity_id=getattr(instance, "id", None),
        actor_user_id=actor,
        request_id=request_id,
        before=before,
        after=after,
    )


def _snapshot_after(state: Any) -> dict[str, Any]:
    """Current column values, skipping relationships and timestamp clutter."""
    out: dict[str, Any] = {}
    for prop in state.mapper.column_attrs:
        if prop.key in _SKIP_KEYS:
            continue
        value = state.attrs[prop.key].loaded_value
        if value is NO_VALUE:
            continue
        out[prop.key] = _coerce(value)
    return out


def _snapshot_update(state: Any) -> tuple[dict[str, Any], dict[str, Any]]:
    """Pre- and post-flush column values for an update.

    Walks ``state.get_history`` per column so we capture the *original*
    value (from ``deleted``) when an attribute changed, falling back to
    ``unchanged`` otherwise. The "after" side is the current loaded value.
    """
    before: dict[str, Any] = {}
    after: dict[str, Any] = {}
    for prop in state.mapper.column_attrs:
        if prop.key in _SKIP_KEYS:
            continue
        history = state.attrs[prop.key].history
        if history.deleted:
            before[prop.key] = _coerce(history.deleted[0])
        elif history.unchanged:
            before[prop.key] = _coerce(history.unchanged[0])

        current = state.attrs[prop.key].loaded_value
        if current is not NO_VALUE:
            after[prop.key] = _coerce(current)
    return before, after


def _coerce(value: Any) -> Any:
    """Make a value JSON-serialisable; bytes → hex, datetime → ISO, else str."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
