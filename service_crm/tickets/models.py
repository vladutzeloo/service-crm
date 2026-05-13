"""Ticket-domain models.

Per ROADMAP 0.5.0:

- :class:`TicketType` — lookup (``incident``, ``preventive``, …).
- :class:`TicketPriority` — lookup (``low``, ``normal``, ``high``, ``urgent``).
- :class:`ServiceTicket` — the ticket header.
- :class:`TicketStatusHistory` — append-only audit of status changes.
- :class:`TicketComment` — free-text comment, plain text (no Markdown).
- :class:`TicketAttachment` — file uploaded against a ticket.

The status enum lives in :mod:`service_crm.tickets.state` (pure Python).
The status-history audit row is written by a ``before_flush`` listener
in :mod:`service_crm.shared.audit` so any code path that mutates
``ServiceTicket.status`` produces history automatically.

``TicketStatusHistory`` does **not** inherit ``Auditable``: it *is* the
audit. Adding ``created_at`` / ``updated_at`` would be redundant with
``occurred_at`` and would also make the row eligible for the
:class:`AuditEvent` listener, producing audit-of-audit rows.
"""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..auth.models import User
from ..clients.models import Client
from ..equipment.models import Equipment
from ..extensions import db
from ..shared import clock, ulid
from ..shared.audit import Auditable
from . import _translations as _t
from .state import TicketStatus

if TYPE_CHECKING:  # pragma: no cover - typing only
    from .intervention_models import ServiceIntervention


class TicketType(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Type lookup — ``incident``, ``preventive``, ``commissioning``, …"""

    __tablename__ = "ticket_type"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("code", name="uq_ticket_type_code"),)

    @property
    def display_label(self) -> str:
        """Translated label, falling back to the stored ``label`` then ``code``.

        Safe to call outside a request context: when ``flask_babel`` can
        not resolve a locale we return the raw English label / code
        rather than raising.
        """
        try:
            translated = _t.type_label(self.code)
        except RuntimeError:
            translated = self.code
        if translated != self.code:
            return translated
        return self.label or self.code

    def __repr__(self) -> str:
        return f"<TicketType {self.code!r}>"


class TicketPriority(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Priority lookup — ``low``, ``normal``, ``high``, ``urgent``."""

    __tablename__ = "ticket_priority"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    rank: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (UniqueConstraint("code", name="uq_ticket_priority_code"),)

    @property
    def display_label(self) -> str:
        try:
            translated = _t.priority_label(self.code)
        except RuntimeError:
            translated = self.code
        if translated != self.code:
            return translated
        return self.label or self.code

    def __repr__(self) -> str:
        return f"<TicketPriority {self.code!r}>"


class ServiceTicket(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """The ticket header.

    ``status`` is stored as a stable English string (``new``,
    ``qualified``, …) — the values of :class:`TicketStatus`. The state
    machine in :mod:`service_crm.tickets.state` is the source of truth
    for legal transitions; the route layer calls it through
    :func:`services.transition_ticket`. Bypassing the service layer (a
    direct ``ticket.status = …`` assignment) still produces a history
    row because the ``before_flush`` listener watches the column.
    """

    __tablename__ = "service_ticket"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    number: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    client_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    equipment_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    type_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("ticket_type.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    priority_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("ticket_priority.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    assignee_user_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")

    status: Mapped[str] = mapped_column(
        String(40), nullable=False, default=TicketStatus.NEW.value, index=True
    )

    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    sla_due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    client: Mapped[Client] = relationship("Client")
    equipment: Mapped[Equipment | None] = relationship("Equipment")
    type: Mapped[TicketType | None] = relationship("TicketType")
    priority: Mapped[TicketPriority | None] = relationship("TicketPriority")
    assignee: Mapped[User | None] = relationship("User")

    history: Mapped[list[TicketStatusHistory]] = relationship(
        "TicketStatusHistory",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketStatusHistory.occurred_at",
    )
    comments: Mapped[list[TicketComment]] = relationship(
        "TicketComment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketComment.created_at",
    )
    attachments: Mapped[list[TicketAttachment]] = relationship(
        "TicketAttachment",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="desc(TicketAttachment.created_at)",
    )
    interventions: Mapped[list[ServiceIntervention]] = relationship(
        "ServiceIntervention",
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="desc(ServiceIntervention.started_at)",
    )

    @property
    def status_enum(self) -> TicketStatus:
        return TicketStatus(self.status)

    @property
    def label(self) -> str:
        """Human-friendly identifier for breadcrumbs."""
        return f"T-{self.number:06d}"

    @property
    def is_terminal(self) -> bool:
        return self.status in {TicketStatus.CLOSED.value, TicketStatus.CANCELLED.value}

    def __repr__(self) -> str:
        return f"<ServiceTicket {self.label} {self.status!r}>"


class TicketStatusHistory(db.Model):  # type: ignore[name-defined,misc]
    """Append-only history row for every status change on a ticket.

    Created via the ``before_flush`` listener in
    :mod:`service_crm.shared.audit` — any code that mutates
    ``ServiceTicket.status`` automatically gets a row here, even if it
    bypasses :func:`services.transition_ticket`.
    """

    __tablename__ = "ticket_status_history"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    ticket_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    from_state: Mapped[str | None] = mapped_column(String(40), nullable=True)
    to_state: Mapped[str] = mapped_column(String(40), nullable=False)
    actor_user_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    reason: Mapped[str] = mapped_column(Text, nullable=False, default="")
    reason_code: Mapped[str] = mapped_column(String(40), nullable=False, default="")
    occurred_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=clock.now, index=True
    )

    ticket: Mapped[ServiceTicket] = relationship("ServiceTicket", back_populates="history")
    actor: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<TicketStatusHistory {self.from_state!r} → {self.to_state!r} @ {self.occurred_at}>"


class TicketComment(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Plain-text comment on a ticket.

    No Markdown, no mentions, no edit history. Body is capped at 8 KB so
    the audit ``before/after`` JSON stays sensible.
    """

    __tablename__ = "ticket_comment"

    BODY_MAX_BYTES = 8192

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    ticket_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    author_user_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    body: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    ticket: Mapped[ServiceTicket] = relationship("ServiceTicket", back_populates="comments")
    author: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<TicketComment id={self.id.hex()[:8]} ticket={self.ticket_id.hex()[:8]}>"


class TicketAttachment(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """File uploaded against a ticket.

    Bytes live on disk under
    ``instance/uploads/tickets/<ticket_hex>/<attachment_ulid><ext>``;
    metadata only is stored here. Streamed back through the route layer
    after an auth check — never linked from ``static/``.
    """

    __tablename__ = "ticket_attachment"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    ticket_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intervention_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    uploader_user_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    filename: Mapped[str] = mapped_column(String(200), nullable=False)
    content_type: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    storage_key: Mapped[str] = mapped_column(String(400), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    ticket: Mapped[ServiceTicket] = relationship("ServiceTicket", back_populates="attachments")
    uploader: Mapped[User | None] = relationship("User")

    def __repr__(self) -> str:
        return f"<TicketAttachment {self.filename!r}>"
