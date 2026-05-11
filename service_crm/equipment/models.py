"""Equipment-domain models.

Per ROADMAP 0.4.0:

- :class:`EquipmentControllerType` — controller lookup (Fanuc, Siemens, …).
- :class:`EquipmentModel` — manufacturer + model lookup, optionally linked
  to a default controller type.
- :class:`Equipment` — installed-base instance, attached to a ``Client``
  and optionally to one of that client's ``Location`` rows.
- :class:`EquipmentWarranty` — warranty record per equipment, with a
  CHECK constraint that ``ends_on > starts_on``.

The cross-row guard "``Equipment.location_id`` must belong to
``Equipment.client_id``" lives in the service layer (see
``service_crm.equipment.services``) and is covered by an integration
test — it's awkward to express as a single SQL CHECK without
denormalising columns.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..clients.models import Client, Location
from ..extensions import db
from ..shared import ulid
from ..shared.audit import Auditable


class EquipmentControllerType(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Controller lookup — Fanuc, Siemens, Heidenhain, Haas, Mitsubishi, …"""

    __tablename__ = "equipment_controller_type"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    code: Mapped[str] = mapped_column(String(40), nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    __table_args__ = (UniqueConstraint("code", name="uq_equipment_controller_type_code"),)

    def __repr__(self) -> str:
        return f"<EquipmentControllerType {self.code!r}>"


class EquipmentModel(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Manufacturer + model code lookup."""

    __tablename__ = "equipment_model"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    manufacturer: Mapped[str] = mapped_column(String(120), nullable=False)
    model_code: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    controller_type_id: Mapped[bytes | None] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment_controller_type.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    controller_type: Mapped[EquipmentControllerType | None] = relationship(
        "EquipmentControllerType",
    )

    __table_args__ = (
        UniqueConstraint("manufacturer", "model_code", name="uq_equipment_model_manuf_code"),
    )

    @property
    def label(self) -> str:
        if self.display_name:
            return self.display_name
        return f"{self.manufacturer} {self.model_code}".strip()

    def __repr__(self) -> str:
        return f"<EquipmentModel {self.manufacturer} {self.model_code}>"


class Equipment(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """An installed CNC machine / asset."""

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
    serial_number: Mapped[str] = mapped_column(String(120), nullable=False, default="", index=True)
    asset_tag: Mapped[str] = mapped_column(String(80), nullable=False, default="", index=True)
    install_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, index=True)

    client: Mapped[Client] = relationship("Client")
    location: Mapped[Location | None] = relationship("Location")
    equipment_model: Mapped[EquipmentModel | None] = relationship("EquipmentModel")
    controller_type: Mapped[EquipmentControllerType | None] = relationship(
        "EquipmentControllerType"
    )

    warranties: Mapped[list[EquipmentWarranty]] = relationship(
        "EquipmentWarranty",
        back_populates="equipment",
        cascade="all, delete-orphan",
        order_by="desc(EquipmentWarranty.starts_on)",
    )

    @property
    def label(self) -> str:
        """Human-friendly identifier used in lists and breadcrumbs."""
        if self.asset_tag:
            return self.asset_tag
        if self.serial_number:
            return self.serial_number
        if self.equipment_model is not None:
            return self.equipment_model.label
        return "equipment"

    def __repr__(self) -> str:
        return f"<Equipment {self.label!r}>"


class EquipmentWarranty(db.Model, Auditable):  # type: ignore[name-defined,misc]
    """Warranty period attached to an :class:`Equipment` row."""

    __tablename__ = "equipment_warranty"

    id: Mapped[bytes] = mapped_column(ulid.ULID, primary_key=True, default=ulid.new)
    equipment_id: Mapped[bytes] = mapped_column(
        ulid.ULID,
        ForeignKey("equipment.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    reference: Mapped[str] = mapped_column(String(120), nullable=False, default="")
    provider: Mapped[str] = mapped_column(String(160), nullable=False, default="")
    starts_on: Mapped[date] = mapped_column(Date, nullable=False)
    ends_on: Mapped[date] = mapped_column(Date, nullable=False)
    notes: Mapped[str] = mapped_column(Text, nullable=False, default="")

    equipment: Mapped[Equipment] = relationship("Equipment", back_populates="warranties")

    __table_args__ = (
        CheckConstraint(
            "ends_on > starts_on",
            name="ck_equipment_warranty_dates",
        ),
    )

    def __repr__(self) -> str:
        return f"<EquipmentWarranty {self.reference!r}>"
