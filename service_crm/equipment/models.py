"""Equipment-domain models.

Four entities:

- ``EquipmentModel``        — manufacturer + model lookup (no Auditable; lookup table).
- ``EquipmentControllerType`` — controller family lookup (no Auditable; lookup table).
- ``Equipment``             — installed CNC machine or asset (soft-delete via is_active).
- ``EquipmentWarranty``     — warranty period per equipment unit.

Guard rules (enforced in services.py):
- ``Equipment.location_id``, when set, must reference a ``Location`` whose
  ``client_id`` matches ``Equipment.client_id``.
- ``EquipmentWarranty.ends_on > starts_on`` — also a DB-level CHECK.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..extensions import db
from ..shared import ulid
from ..shared.audit import Auditable


class EquipmentModel(db.Model):  # type: ignore[name-defined,misc]
    """Manufacturer + CNC model lookup — seed via CSV or admin UI."""

    __tablename__ = "equipment_model"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False)
    model: Mapped[str] = mapped_column(String(120), nullable=False)
    family: Mapped[str] = mapped_column(String(120), nullable=False, default="")

    equipment: Mapped[list[Equipment]] = relationship("Equipment", back_populates="equipment_model")

    __table_args__ = (UniqueConstraint("manufacturer", "model", name="uq_equipment_model"),)

    def __repr__(self) -> str:
        return f"<EquipmentModel {self.manufacturer!r} {self.model!r}>"


class EquipmentControllerType(db.Model):  # type: ignore[name-defined,misc]
    """CNC controller family lookup (Fanuc, Siemens, Heidenhain, Haas, …)."""

    __tablename__ = "equipment_controller_type"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(60), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)

    equipment: Mapped[list[Equipment]] = relationship("Equipment", back_populates="controller_type")

    def __repr__(self) -> str:
        return f"<EquipmentControllerType {self.code!r}>"


class Equipment(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """An installed CNC machine, asset, or unit at a client site."""

    __tablename__ = "equipment"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    client_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("client.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    location_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("location.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    equipment_model_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment_model.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    controller_type_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment_controller_type.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    serial: Mapped[str | None] = mapped_column(String(120), unique=True, nullable=True)
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    model: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    installed_at: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    client: Mapped[Client] = relationship("Client", back_populates="equipment")  # type: ignore[name-defined]  # noqa: F821
    location: Mapped[Location | None] = relationship("Location", back_populates="equipment")  # type: ignore[name-defined]  # noqa: F821
    equipment_model: Mapped[EquipmentModel | None] = relationship(
        "EquipmentModel", back_populates="equipment"
    )
    controller_type: Mapped[EquipmentControllerType | None] = relationship(
        "EquipmentControllerType", back_populates="equipment"
    )
    warranties: Mapped[list[EquipmentWarranty]] = relationship(
        "EquipmentWarranty", back_populates="equipment", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Equipment {self.name!r}>"


class EquipmentWarranty(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Warranty period for a single equipment unit."""

    __tablename__ = "equipment_warranty"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    equipment_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    coverage: Mapped[str] = mapped_column(Text, nullable=False, default="")

    equipment: Mapped[Equipment] = relationship("Equipment", back_populates="warranties")

    __table_args__ = (CheckConstraint("ends_on > starts_on", name="ck_equipment_warranty_dates"),)

    def __repr__(self) -> str:
        return f"<EquipmentWarranty {self.starts_on}-{self.ends_on}>"
