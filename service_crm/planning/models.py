"""Planning-domain models — ROADMAP 0.7.0.

Per [`docs/architecture-plan.md`](../../docs/architecture-plan.md) §4.1:

- :class:`Technician` — 1:1 with :class:`User`.
- :class:`TechnicianAssignment` — joins a technician to a ticket and/or
  intervention.
- :class:`TechnicianCapacitySlot` — per-day declared minutes.

All inherit :class:`Auditable`.
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

from ..auth.models import User
from ..extensions import db
from ..shared import clock, ulid
from ..shared.audit import Auditable

if TYPE_CHECKING:  # pragma: no cover - typing only
    from ..tickets.intervention_models import ServiceIntervention
    from ..tickets.models import ServiceTicket


class Technician(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Planning-side mirror of a :class:`User`.

    Soft-deletable via ``is_active`` so historical assignments keep
    rendering even after a technician leaves.
    """

    __tablename__ = "technician"

    DEFAULT_WEEKLY_MINUTES = 2400  # 40h x 60

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    user_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("user_account.id", ondelete="CASCADE"),
        nullable=False,
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    timezone: Mapped[str] = mapped_column(String(60), nullable=False, default="Europe/Bucharest")
    weekly_capacity_minutes: Mapped[int] = mapped_column(
        Integer, nullable=False, default=DEFAULT_WEEKLY_MINUTES
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    __table_args__ = (
        UniqueConstraint("user_id", name="uq_technician_user_id"),
        CheckConstraint(
            "weekly_capacity_minutes >= 0",
            name="ck_technician_weekly_capacity_non_negative",
        ),
    )

    user: Mapped[User] = relationship("User")
    capacity_slots: Mapped[list[TechnicianCapacitySlot]] = relationship(
        "TechnicianCapacitySlot",
        back_populates="technician",
        cascade="all, delete-orphan",
        order_by="TechnicianCapacitySlot.day",
    )
    assignments: Mapped[list[TechnicianAssignment]] = relationship(
        "TechnicianAssignment",
        back_populates="technician",
        cascade="all, delete-orphan",
        order_by="TechnicianAssignment.assigned_at",
    )

    @property
    def label(self) -> str:
        return self.display_name or (self.user.email if self.user else "")

    def __repr__(self) -> str:
        return f"<Technician {self.label!r}>"


class TechnicianAssignment(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Ticket / intervention assignment.

    At least one of ``ticket_id`` or ``intervention_id`` must be set;
    the CHECK below makes "neither" illegal at the DB level. Both can
    be set simultaneously when a technician is assigned to a specific
    intervention on a specific ticket — explicit, not an error.
    """

    __tablename__ = "technician_assignment"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    technician_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("technician.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    ticket_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_ticket.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    intervention_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("service_intervention.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    assigned_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=clock.now
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        CheckConstraint(
            "ticket_id IS NOT NULL OR intervention_id IS NOT NULL",
            name="ck_technician_assignment_target",
        ),
    )

    technician: Mapped[Technician] = relationship("Technician", back_populates="assignments")
    ticket: Mapped[ServiceTicket | None] = relationship("ServiceTicket")
    intervention: Mapped[ServiceIntervention | None] = relationship("ServiceIntervention")

    def __repr__(self) -> str:
        target = "intervention" if self.intervention_id else "ticket"
        return f"<TechnicianAssignment {target} tech={self.technician_id.hex()[:8]}>"


class TechnicianCapacitySlot(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Declared minutes available on a given day."""

    __tablename__ = "technician_capacity_slot"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    technician_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("technician.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    day: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    capacity_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (
        UniqueConstraint("technician_id", "day", name="uq_technician_capacity_slot_day"),
        CheckConstraint(
            "capacity_minutes >= 0",
            name="ck_technician_capacity_slot_non_negative",
        ),
    )

    technician: Mapped[Technician] = relationship("Technician", back_populates="capacity_slots")

    def __repr__(self) -> str:
        return f"<TechnicianCapacitySlot {self.day} {self.capacity_minutes}min>"


__all__ = [
    "Technician",
    "TechnicianAssignment",
    "TechnicianCapacitySlot",
]
