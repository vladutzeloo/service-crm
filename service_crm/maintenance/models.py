"""Maintenance-domain models — ROADMAP 0.7.0.

Per [`docs/architecture-plan.md`](../../docs/architecture-plan.md) §4.1
and the resolutions in [`docs/v0.7-plan.md`](../../docs/v0.7-plan.md):

- :class:`MaintenanceTemplate` — reusable recipe. ``cadence_days`` is
  the default for plans built from this template; plans can override.
- :class:`MaintenancePlan` — per-equipment schedule. ``next_due_on`` is
  derived (set by the service layer / scheduler), never written by
  routes directly.
- :class:`MaintenanceTask` — one open task per plan; status is
  ``pending`` → ``done`` (via an execution) or ``pending`` →
  ``escalated`` (via the new-ticket button).
- :class:`MaintenanceExecution` — completion record, links back to a
  :class:`ServiceIntervention` so technician work is reusable.

All four inherit :class:`Auditable`.
"""

from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..equipment.models import Equipment
from ..extensions import db
from ..shared import clock, ulid
from ..shared.audit import Auditable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..knowledge.models import ChecklistTemplate
    from ..planning.models import Technician
    from ..tickets.intervention_models import ServiceIntervention
    from ..tickets.models import ServiceTicket


class TaskStatus:
    """Stable English string codes for :attr:`MaintenanceTask.status`.

    Stored as ``String(20)`` (not ``SAEnum``) so adding ``cancelled``
    later doesn't require a migration. The translations live in
    :mod:`._translations`.
    """

    PENDING = "pending"
    DONE = "done"
    ESCALATED = "escalated"

    ALL: frozenset[str] = frozenset({PENDING, DONE, ESCALATED})


class MaintenanceTemplate(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Reusable maintenance recipe."""

    __tablename__ = "maintenance_template"

    NAME_MAX = 200

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    name: Mapped[str] = mapped_column(String(NAME_MAX), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False, default=180)
    estimated_minutes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checklist_template_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("checklist_template.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("name", name="uq_maintenance_template_name"),
        CheckConstraint("cadence_days > 0", name="ck_maintenance_template_cadence_positive"),
    )

    checklist_template: Mapped[ChecklistTemplate | None] = relationship("ChecklistTemplate")
    # No ``delete``/``delete-orphan`` cascade: the FK on
    # ``maintenance_plan.template_id`` uses ``ondelete="RESTRICT"``, so
    # deleting a template with live plans is an error by design. The ORM
    # cascade would race the DB constraint and turn the friendly
    # ValueError into an opaque IntegrityError.
    plans: Mapped[list[MaintenancePlan]] = relationship(
        "MaintenancePlan",
        back_populates="template",
        order_by="MaintenancePlan.created_at",
    )

    def __repr__(self) -> str:
        return f"<MaintenanceTemplate {self.name!r}>"


class MaintenancePlan(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """A maintenance recipe scheduled against a piece of equipment.

    ``next_due_on`` is set by :func:`services.recompute_plan` (also run
    by the APScheduler tick) — routes never write it directly.
    """

    __tablename__ = "maintenance_plan"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    equipment_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    template_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("maintenance_template.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    cadence_days: Mapped[int] = mapped_column(Integer, nullable=False)
    last_done_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    next_due_on: Mapped[date | None] = mapped_column(Date, nullable=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        CheckConstraint("cadence_days > 0", name="ck_maintenance_plan_cadence_positive"),
    )

    equipment: Mapped[Equipment] = relationship("Equipment")
    template: Mapped[MaintenanceTemplate] = relationship(
        "MaintenanceTemplate", back_populates="plans"
    )
    tasks: Mapped[list[MaintenanceTask]] = relationship(
        "MaintenanceTask",
        back_populates="plan",
        cascade="all, delete-orphan",
        order_by="MaintenanceTask.due_on",
    )

    @property
    def is_overdue(self) -> bool:
        if self.next_due_on is None:
            return False
        return self.next_due_on < clock.now().date()

    def __repr__(self) -> str:
        return f"<MaintenancePlan id={self.id.hex()[:8]} due={self.next_due_on}>"


class MaintenanceTask(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """A generated occurrence of a plan due-date.

    One row per "due-ness" — the scheduler only generates a new task
    when the previous one is ``done`` or ``escalated`` (see
    :func:`services.generate_pending_tasks`).
    """

    __tablename__ = "maintenance_task"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    plan_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("maintenance_plan.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    due_on: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=TaskStatus.PENDING, index=True
    )
    assigned_technician_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("technician.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    ticket_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    plan: Mapped[MaintenancePlan] = relationship("MaintenancePlan", back_populates="tasks")
    ticket: Mapped[ServiceTicket | None] = relationship("ServiceTicket")
    assigned_technician: Mapped[Technician | None] = relationship("Technician")
    executions: Mapped[list[MaintenanceExecution]] = relationship(
        "MaintenanceExecution",
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="MaintenanceExecution.completed_at",
    )

    @property
    def is_overdue(self) -> bool:
        if self.status != TaskStatus.PENDING:
            return False
        return self.due_on < clock.now().date()

    @property
    def is_done(self) -> bool:
        return self.status == TaskStatus.DONE

    def __repr__(self) -> str:
        return f"<MaintenanceTask id={self.id.hex()[:8]} status={self.status!r}>"


class MaintenanceExecution(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Record that a task was completed.

    Inserting a row flips the parent task's ``status`` to ``done``
    (service-layer rule; the route layer calls
    :func:`services.complete_task`).
    """

    __tablename__ = "maintenance_execution"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    task_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("maintenance_task.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    intervention_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    completed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=clock.now
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    task: Mapped[MaintenanceTask] = relationship("MaintenanceTask", back_populates="executions")
    intervention: Mapped[ServiceIntervention | None] = relationship("ServiceIntervention")

    def __repr__(self) -> str:
        return f"<MaintenanceExecution id={self.id.hex()[:8]} task={self.task_id.hex()[:8]}>"


__all__ = [
    "MaintenanceExecution",
    "MaintenancePlan",
    "MaintenanceTask",
    "MaintenanceTemplate",
    "TaskStatus",
]
