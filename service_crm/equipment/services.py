"""Service layer for the equipment blueprint.

Guard rules enforced here (not in models):
- ``Equipment.location_id``, when set, must reference a ``Location``
  whose ``client_id`` matches ``Equipment.client_id``.
- ``EquipmentWarranty.ends_on > starts_on`` — validated before INSERT/UPDATE.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy.orm import Session

from ..clients.models import Location
from .models import Equipment, EquipmentControllerType, EquipmentModel, EquipmentWarranty


def _check_location_ownership(
    session: Session, client_id: bytes, location_id: bytes | None
) -> None:
    """Raise ValueError if location_id is set but belongs to a different client."""
    if location_id is None:
        return
    loc = session.get(Location, location_id)
    if loc is None or loc.client_id != client_id:
        raise ValueError("location_id must belong to the same client as the equipment.")


def _check_warranty_dates(starts_on: date, ends_on: date) -> None:
    if ends_on <= starts_on:
        raise ValueError("ends_on must be after starts_on.")


# ── Equipment ─────────────────────────────────────────────────────────────────


def create_equipment(
    session: Session,
    *,
    client_id: bytes,
    name: str,
    location_id: bytes | None = None,
    equipment_model_id: bytes | None = None,
    controller_type_id: bytes | None = None,
    serial: str | None = None,
    manufacturer: str = "",
    model: str = "",
    installed_at: date | None = None,
    notes: str = "",
) -> Equipment:
    _check_location_ownership(session, client_id, location_id)
    equip = Equipment(
        client_id=client_id,
        location_id=location_id,
        equipment_model_id=equipment_model_id,
        controller_type_id=controller_type_id,
        name=name.strip(),
        serial=serial or None,
        manufacturer=manufacturer.strip(),
        model=model.strip(),
        installed_at=installed_at,
        notes=notes.strip(),
    )
    session.add(equip)
    session.flush()
    return equip


def update_equipment(
    session: Session,
    equip: Equipment,
    *,
    name: str,
    location_id: bytes | None = None,
    equipment_model_id: bytes | None = None,
    controller_type_id: bytes | None = None,
    serial: str | None = None,
    manufacturer: str = "",
    model: str = "",
    installed_at: date | None = None,
    notes: str = "",
) -> None:
    _check_location_ownership(session, equip.client_id, location_id)
    equip.name = name.strip()
    equip.location_id = location_id
    equip.equipment_model_id = equipment_model_id
    equip.controller_type_id = controller_type_id
    equip.serial = serial or None
    equip.manufacturer = manufacturer.strip()
    equip.model = model.strip()
    equip.installed_at = installed_at
    equip.notes = notes.strip()


def deactivate_equipment(session: Session, equip: Equipment) -> None:
    equip.is_active = False


def reactivate_equipment(session: Session, equip: Equipment) -> None:
    equip.is_active = True


def get_equipment(session: Session, equipment_id: bytes) -> Equipment | None:
    return session.get(Equipment, equipment_id)


def require_equipment(session: Session, hex_id: str) -> Equipment:
    try:
        raw = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid equipment id: {hex_id!r}") from exc
    equip = session.get(Equipment, raw)
    if equip is None:
        raise ValueError(f"Equipment {hex_id!r} not found.")
    return equip


def list_equipment(
    session: Session,
    *,
    client_id: bytes | None = None,
    active_only: bool = True,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Equipment], int]:
    q = session.query(Equipment)
    if client_id is not None:
        q = q.filter(Equipment.client_id == client_id)
    if active_only:
        q = q.filter(Equipment.is_active.is_(True))
    total = q.count()
    items = q.order_by(Equipment.name).offset(max(0, page - 1) * per_page).limit(per_page).all()
    return items, total


# ── Warranties ────────────────────────────────────────────────────────────────


def create_warranty(
    session: Session,
    *,
    equipment_id: bytes,
    starts_on: date,
    ends_on: date,
    coverage: str = "",
) -> EquipmentWarranty:
    _check_warranty_dates(starts_on, ends_on)
    w = EquipmentWarranty(
        equipment_id=equipment_id,
        starts_on=starts_on,
        ends_on=ends_on,
        coverage=coverage.strip(),
    )
    session.add(w)
    session.flush()
    return w


def update_warranty(
    session: Session,
    warranty: EquipmentWarranty,
    *,
    starts_on: date,
    ends_on: date,
    coverage: str = "",
) -> None:
    _check_warranty_dates(starts_on, ends_on)
    warranty.starts_on = starts_on
    warranty.ends_on = ends_on
    warranty.coverage = coverage.strip()


def delete_warranty(session: Session, warranty: EquipmentWarranty) -> None:
    session.delete(warranty)
    session.flush()


def require_warranty(session: Session, hex_id: str, equip: Equipment) -> EquipmentWarranty:
    try:
        raw = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid warranty id: {hex_id!r}") from exc
    w = session.get(EquipmentWarranty, raw)
    if w is None or w.equipment_id != equip.id:
        raise ValueError(f"Warranty {hex_id!r} not found.")
    return w


# ── Lookup tables ─────────────────────────────────────────────────────────────


def list_controller_types(session: Session) -> list[EquipmentControllerType]:
    return session.query(EquipmentControllerType).order_by(EquipmentControllerType.name).all()


def list_equipment_models(session: Session) -> list[EquipmentModel]:
    return (
        session.query(EquipmentModel)
        .order_by(EquipmentModel.manufacturer, EquipmentModel.model)
        .all()
    )
