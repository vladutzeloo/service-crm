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
def _record_audit_events(session: Session, _flush_ctx: Any, _instances: Any) -> None:
    if not _audit_enabled():
        return

    actor = ACTOR_CTX.get()
    request_id = REQUEST_ID_CTX.get()

    pending: list[AuditEvent] = []
    for instance in session.new:
        if isinstance(instance, Auditable) and not isinstance(instance, AuditEvent):
            pending.append(_event_for(instance, "create", actor, request_id))
    for instance in session.dirty:
        if (
            isinstance(instance, Auditable)
            and not isinstance(instance, AuditEvent)
            and session.is_modified(instance, include_collections=False)
        ):
            pending.append(_event_for(instance, "update", actor, request_id))
    for instance in session.deleted:
        if isinstance(instance, Auditable) and not isinstance(instance, AuditEvent):
            pending.append(_event_for(instance, "delete", actor, request_id))

    for evt in pending:
        session.add(evt)


def _audit_enabled() -> bool:
    if not has_app_context():
        return False
    return bool(current_app.config.get("AUDIT_LOG_ENABLED", True))


def _event_for(
    instance: Any,
    action: str,
    actor: bytes | None,
    request_id: str | None,
) -> AuditEvent:
    state = inspect(instance)
    after: dict[str, Any] = {}
    for attr in state.attrs:
        if attr.key in {"created_at", "updated_at"}:
            continue
        try:
            after[attr.key] = _coerce(attr.loaded_value)
        except Exception:
            after[attr.key] = None

    return AuditEvent(
        action=action,
        entity_type=type(instance).__name__,
        entity_id=getattr(instance, "id", None),
        actor_user_id=actor,
        request_id=request_id,
        before=None,
        after=after if action != "delete" else None,
    )


def _coerce(value: Any) -> Any:
    """Make a value JSON-serialisable; bytes → hex, datetime → ISO, else str."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, bytes):
        return value.hex()
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)
