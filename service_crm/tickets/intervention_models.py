"""Intervention-domain models — ROADMAP 0.6.0.

Adds the five intervention / parts tables to the ``tickets`` blueprint
per [`docs/architecture-plan.md`](../../docs/architecture-plan.md) §4.1:

- :class:`ServiceIntervention` — a single field-job session on a
  ticket; ``started_at`` is required, ``ended_at`` flips when the
  technician stops.
- :class:`InterventionAction` — discrete action performed (e.g.
  "replaced spindle bearing"). Free text in v0.6; templated actions
  arrive in v1.3.
- :class:`InterventionFinding` — observation / diagnosis. Carries an
  ``is_root_cause`` boolean so the report layer in v0.8 can roll up
  recurring causes.
- :class:`PartMaster` — lightweight catalog of replaceable parts.
  Soft-deleted via ``is_active``; not a warehouse (per
  [`docs/blueprint.md`](../../docs/blueprint.md) §2 out-of-scope).
- :class:`ServicePartUsage` — per-intervention part draw. Allows
  duplicate ``(intervention_id, part_id)`` rows; the display layer
  coalesces.

The models live in a separate module to keep ``models.py`` reviewable;
they're re-exported from :mod:`service_crm.tickets` so external imports
stay stable.
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
from ..extensions import db
from ..shared import clock, ulid
from ..shared.audit import Auditable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..knowledge.models import ChecklistRun
    from .models import ServiceTicket


class ServiceIntervention(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """A single technician session on a ticket.

    Multiple interventions per ticket are normal — a return visit, a
    re-attempt after waiting for parts, a follow-up monitoring run all
    create their own intervention row. The ticket FSM in
    :mod:`service_crm.tickets.state` is unaffected; interventions
    represent recorded work, not workflow state.
    """

    __tablename__ = "service_intervention"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    ticket_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    technician_user_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=clock.now, index=True
    )
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    summary: Mapped[str] = mapped_column(Text, nullable=False, default="")

    ticket: Mapped[ServiceTicket] = relationship(
        "ServiceTicket",
        back_populates="interventions",
    )
    technician: Mapped[User | None] = relationship("User")
    actions: Mapped[list[InterventionAction]] = relationship(
        "InterventionAction",
        back_populates="intervention",
        cascade="all, delete-orphan",
        order_by="InterventionAction.created_at",
    )
    findings: Mapped[list[InterventionFinding]] = relationship(
        "InterventionFinding",
        back_populates="intervention",
        cascade="all, delete-orphan",
        order_by="InterventionFinding.created_at",
    )
    parts: Mapped[list[ServicePartUsage]] = relationship(
        "ServicePartUsage",
        back_populates="intervention",
        cascade="all, delete-orphan",
        order_by="ServicePartUsage.created_at",
    )
    checklist_runs: Mapped[list[ChecklistRun]] = relationship(
        "ChecklistRun",
        back_populates="intervention",
        cascade="all, delete-orphan",
        order_by="ChecklistRun.created_at",
    )

    @property
    def is_open(self) -> bool:
        return self.ended_at is None

    @property
    def duration_minutes(self) -> int | None:
        """Whole minutes elapsed, or ``None`` if still open."""
        if self.ended_at is None:
            return None
        delta = self.ended_at - self.started_at
        return max(0, int(delta.total_seconds() // 60))

    def __repr__(self) -> str:
        return f"<ServiceIntervention id={self.id.hex()[:8]} open={self.is_open}>"


class InterventionAction(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """A discrete action performed during an intervention."""

    __tablename__ = "intervention_action"

    DESCRIPTION_MAX_BYTES = 4096

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    intervention_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    duration_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)

    intervention: Mapped[ServiceIntervention] = relationship(
        "ServiceIntervention", back_populates="actions"
    )

    def __repr__(self) -> str:
        return f"<InterventionAction id={self.id.hex()[:8]}>"


class InterventionFinding(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """An observation or diagnosis recorded during an intervention."""

    __tablename__ = "intervention_finding"

    DESCRIPTION_MAX_BYTES = 4096

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    intervention_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_root_cause: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, index=True)

    intervention: Mapped[ServiceIntervention] = relationship(
        "ServiceIntervention", back_populates="findings"
    )

    def __repr__(self) -> str:
        return f"<InterventionFinding id={self.id.hex()[:8]} root={self.is_root_cause}>"


class PartMaster(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Lightweight catalog of replaceable parts.

    Not a warehouse — there's no stock tracking, no costing, no
    serial-level traceability. Just the bare minimum (``code``,
    ``description``, ``unit``) to make :class:`ServicePartUsage`
    rows readable.
    """

    __tablename__ = "part_master"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (UniqueConstraint("code", name="uq_part_master_code"),)

    usages: Mapped[list[ServicePartUsage]] = relationship("ServicePartUsage", back_populates="part")

    @property
    def label(self) -> str:
        if self.description:
            return f"{self.code} — {self.description}"
        return self.code

    def __repr__(self) -> str:
        return f"<PartMaster {self.code!r}>"


class ServicePartUsage(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """One part draw against an intervention.

    Duplicate ``(intervention_id, part_id)`` rows are allowed — field
    workflows draw the same SKU at different times. ``part_code`` and
    ``description`` are snapshotted so deleting / renaming the
    :class:`PartMaster` row keeps the audit trail readable.
    """

    __tablename__ = "service_part_usage"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    intervention_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    # ``part_id`` is nullable to support ad-hoc usages — a technician
    # records a part draw before the catalog row exists. ``part_code``
    # and ``description`` are always populated so the row is readable
    # even if ``part_id`` later resolves to ``NULL``.
    part_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("part_master.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    part_code: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    quantity: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    unit: Mapped[str] = mapped_column(String(20), nullable=False, default="pcs")

    intervention: Mapped[ServiceIntervention] = relationship(
        "ServiceIntervention", back_populates="parts"
    )
    part: Mapped[PartMaster | None] = relationship("PartMaster", back_populates="usages")

    def __repr__(self) -> str:
        return f"<ServicePartUsage {self.part_code!r} x{self.quantity}>"


__all__ = [
    "InterventionAction",
    "InterventionFinding",
    "PartMaster",
    "ServiceIntervention",
    "ServicePartUsage",
]
