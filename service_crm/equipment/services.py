"""Service layer for the equipment blueprint.

All SQL lives here. The cross-row guard "``Equipment.location_id`` (when
set) must belong to ``Equipment.client_id``" is enforced by
:func:`_validate_location_belongs_to_client` and is exercised by the
integration tests in ``tests/equipment/test_models.py``.

Search is dialect-aware, mirroring the clients-blueprint pattern: a GIN
expression-index covers the Postgres path, SQLite falls back to LIKE.
"""

from __future__ import annotations

import csv
import io
from datetime import date
from typing import Any

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from ..clients.models import Client, Location
from ..extensions import db
from .models import (
    Equipment,
    EquipmentControllerType,
    EquipmentModel,
    EquipmentWarranty,
)

# ── Helpers ──────────────────────────────────────────────────────────────────


def _dialect() -> str:
    return db.engine.dialect.name


def _equipment_search_filter(q: str) -> Any:
    """Return a WHERE expression matching ``serial_number`` / ``asset_tag``.

    The Postgres path uses the same ``to_tsvector('simple', …)`` shape as
    the GIN expression-index created in the migration so the planner
    actually picks the index up.
    """
    q = q.strip()
    if not q:
        return None

    if _dialect() == "postgresql":
        from sqlalchemy import literal_column

        tsq = func.plainto_tsquery(literal_column("'simple'"), q)
        text = (
            func.coalesce(Equipment.serial_number, "")
            + " "
            + func.coalesce(Equipment.asset_tag, "")
        )
        return func.to_tsvector(literal_column("'simple'"), text).op("@@")(tsq)

    pattern = f"%{q.lower()}%"
    return or_(
        func.lower(Equipment.serial_number).like(pattern),
        func.lower(Equipment.asset_tag).like(pattern),
    )


# ── Lookups: controller types ────────────────────────────────────────────────


def list_controller_types(session: Session) -> list[EquipmentControllerType]:
    return session.query(EquipmentControllerType).order_by(EquipmentControllerType.name).all()


def require_controller_type(session: Session, hex_id: str) -> EquipmentControllerType:
    try:
        cid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid controller type id") from exc
    obj = session.get(EquipmentControllerType, cid)
    if obj is None:
        raise ValueError("controller type not found")
    return obj


def create_controller_type(
    session: Session, *, code: str, name: str, notes: str = ""
) -> EquipmentControllerType:
    obj = EquipmentControllerType(code=code.strip(), name=name.strip(), notes=notes.strip())
    session.add(obj)
    session.flush()
    return obj


def update_controller_type(
    session: Session,
    obj: EquipmentControllerType,
    *,
    code: str,
    name: str,
    notes: str = "",
) -> EquipmentControllerType:
    obj.code = code.strip()
    obj.name = name.strip()
    obj.notes = notes.strip()
    session.flush()
    return obj


def delete_controller_type(session: Session, obj: EquipmentControllerType) -> None:
    session.delete(obj)
    session.flush()


# ── Lookups: equipment models ────────────────────────────────────────────────


def list_equipment_models(session: Session) -> list[EquipmentModel]:
    return (
        session.query(EquipmentModel)
        .order_by(EquipmentModel.manufacturer, EquipmentModel.model_code)
        .all()
    )


def require_equipment_model(session: Session, hex_id: str) -> EquipmentModel:
    try:
        mid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid equipment model id") from exc
    obj = session.get(EquipmentModel, mid)
    if obj is None:
        raise ValueError("equipment model not found")
    return obj


def create_equipment_model(
    session: Session,
    *,
    manufacturer: str,
    model_code: str,
    display_name: str = "",
    controller_type_id: bytes | None = None,
    notes: str = "",
) -> EquipmentModel:
    obj = EquipmentModel(
        manufacturer=manufacturer.strip(),
        model_code=model_code.strip(),
        display_name=display_name.strip(),
        controller_type_id=controller_type_id,
        notes=notes.strip(),
    )
    session.add(obj)
    session.flush()
    return obj


def update_equipment_model(
    session: Session,
    obj: EquipmentModel,
    *,
    manufacturer: str,
    model_code: str,
    display_name: str = "",
    controller_type_id: bytes | None = None,
    notes: str = "",
) -> EquipmentModel:
    obj.manufacturer = manufacturer.strip()
    obj.model_code = model_code.strip()
    obj.display_name = display_name.strip()
    obj.controller_type_id = controller_type_id
    obj.notes = notes.strip()
    session.flush()
    return obj


def delete_equipment_model(session: Session, obj: EquipmentModel) -> None:
    session.delete(obj)
    session.flush()


# ── Equipment instances ──────────────────────────────────────────────────────


def list_equipment(
    session: Session,
    *,
    q: str = "",
    client_id: bytes | None = None,
    active_only: bool = True,
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[Equipment], int]:
    """Return (page_items, total_matching_count)."""
    base = session.query(Equipment)
    if active_only:
        base = base.filter(Equipment.is_active.is_(True))
    if client_id is not None:
        base = base.filter(Equipment.client_id == client_id)
    flt = _equipment_search_filter(q)
    if flt is not None:
        base = base.filter(flt)
    total: int = base.count()
    items: list[Equipment] = (
        base.order_by(Equipment.asset_tag, Equipment.serial_number)
        .offset((page - 1) * per_page)
        .limit(per_page)
        .all()
    )
    return items, total


def require_equipment(session: Session, hex_id: str) -> Equipment:
    try:
        eid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid equipment id") from exc
    obj = session.get(Equipment, eid)
    if obj is None:
        raise ValueError("equipment not found")
    return obj


def _validate_location_belongs_to_client(
    session: Session, *, client_id: bytes, location_id: bytes | None
) -> None:
    """Guard the constraint that a location must belong to the same client.

    Pure service-layer check — the FK alone can't express it without
    denormalising ``client_id`` into the ``location`` row. We raise
    ``ValueError`` so the route can flash it as a form error.
    """
    if location_id is None:
        return
    loc = session.get(Location, location_id)
    if loc is None:
        raise ValueError("location not found")
    if loc.client_id != client_id:
        raise ValueError("location does not belong to this client")


def create_equipment(
    session: Session,
    *,
    client_id: bytes,
    location_id: bytes | None = None,
    equipment_model_id: bytes | None = None,
    controller_type_id: bytes | None = None,
    serial_number: str = "",
    asset_tag: str = "",
    install_date: date | None = None,
    notes: str = "",
) -> Equipment:
    if session.get(Client, client_id) is None:
        raise ValueError("client not found")
    _validate_location_belongs_to_client(session, client_id=client_id, location_id=location_id)
    obj = Equipment(
        client_id=client_id,
        location_id=location_id,
        equipment_model_id=equipment_model_id,
        controller_type_id=controller_type_id,
        serial_number=serial_number.strip(),
        asset_tag=asset_tag.strip(),
        install_date=install_date,
        notes=notes.strip(),
    )
    session.add(obj)
    session.flush()
    return obj


def update_equipment(
    session: Session,
    equipment: Equipment,
    *,
    client_id: bytes,
    location_id: bytes | None = None,
    equipment_model_id: bytes | None = None,
    controller_type_id: bytes | None = None,
    serial_number: str = "",
    asset_tag: str = "",
    install_date: date | None = None,
    notes: str = "",
) -> Equipment:
    if session.get(Client, client_id) is None:
        raise ValueError("client not found")
    _validate_location_belongs_to_client(session, client_id=client_id, location_id=location_id)
    equipment.client_id = client_id
    equipment.location_id = location_id
    equipment.equipment_model_id = equipment_model_id
    equipment.controller_type_id = controller_type_id
    equipment.serial_number = serial_number.strip()
    equipment.asset_tag = asset_tag.strip()
    equipment.install_date = install_date
    equipment.notes = notes.strip()
    session.flush()
    return equipment


def deactivate_equipment(session: Session, equipment: Equipment) -> None:
    equipment.is_active = False
    session.flush()


def reactivate_equipment(session: Session, equipment: Equipment) -> None:
    equipment.is_active = True
    session.flush()


# ── Warranties ───────────────────────────────────────────────────────────────


def require_warranty(session: Session, hex_id: str, equipment: Equipment) -> EquipmentWarranty:
    try:
        wid = bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError("invalid warranty id") from exc
    obj = session.get(EquipmentWarranty, wid)
    if obj is None or obj.equipment_id != equipment.id:
        raise ValueError("warranty not found")
    return obj


def create_warranty(
    session: Session,
    *,
    equipment_id: bytes,
    starts_on: date,
    ends_on: date,
    reference: str = "",
    provider: str = "",
    notes: str = "",
) -> EquipmentWarranty:
    if ends_on <= starts_on:
        raise ValueError("ends_on must be after starts_on")
    obj = EquipmentWarranty(
        equipment_id=equipment_id,
        reference=reference.strip(),
        provider=provider.strip(),
        starts_on=starts_on,
        ends_on=ends_on,
        notes=notes.strip(),
    )
    session.add(obj)
    session.flush()
    return obj


def update_warranty(
    session: Session,
    warranty: EquipmentWarranty,
    *,
    starts_on: date,
    ends_on: date,
    reference: str = "",
    provider: str = "",
    notes: str = "",
) -> EquipmentWarranty:
    if ends_on <= starts_on:
        raise ValueError("ends_on must be after starts_on")
    warranty.starts_on = starts_on
    warranty.ends_on = ends_on
    warranty.reference = reference.strip()
    warranty.provider = provider.strip()
    warranty.notes = notes.strip()
    session.flush()
    return warranty


def delete_warranty(session: Session, warranty: EquipmentWarranty) -> None:
    session.delete(warranty)
    session.flush()


# ── CSV imports ──────────────────────────────────────────────────────────────


def _read_rows(text: str, required: set[str]) -> tuple[csv.DictReader[str], list[str]]:
    """Parse CSV header and return (reader, errors).

    Errors are returned as a list so the caller can short-circuit.
    """
    reader = csv.DictReader(io.StringIO(text.strip()))
    if reader.fieldnames is None:
        return reader, ["CSV file is empty or missing a header row."]
    header = {f.strip().lower() for f in reader.fieldnames}
    if not (header >= required):
        missing = sorted(required - header)
        return reader, [f"Missing required columns: {', '.join(missing)}"]
    return reader, []


_CONTROLLER_REQUIRED = {"code", "name"}


def import_controller_types_csv(session: Session, text: str) -> tuple[int, list[str]]:
    reader, errors = _read_rows(text, _CONTROLLER_REQUIRED)
    if errors:
        return 0, errors

    imported = 0
    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v for k, v in raw_row.items() if k}
        code = row.get("code", "").strip()
        name = row.get("name", "").strip()
        if not code or not name:
            errors.append(f"Row {row_num}: code and name are required.")
            continue
        existing = (
            session.query(EquipmentControllerType)
            .filter(EquipmentControllerType.code == code)
            .one_or_none()
        )
        if existing is not None:
            existing.name = name
            existing.notes = row.get("notes", "").strip()
        else:
            create_controller_type(
                session, code=code, name=name, notes=row.get("notes", "").strip()
            )
        imported += 1
    return imported, errors


_MODEL_REQUIRED = {"manufacturer", "model_code"}


def import_equipment_models_csv(session: Session, text: str) -> tuple[int, list[str]]:
    reader, errors = _read_rows(text, _MODEL_REQUIRED)
    if errors:
        return 0, errors

    imported = 0
    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v for k, v in raw_row.items() if k}
        manuf = row.get("manufacturer", "").strip()
        code = row.get("model_code", "").strip()
        if not manuf or not code:
            errors.append(f"Row {row_num}: manufacturer and model_code are required.")
            continue

        ctrl_id: bytes | None = None
        ctrl_code = row.get("controller_code", "").strip()
        if ctrl_code:
            ctrl = (
                session.query(EquipmentControllerType)
                .filter(EquipmentControllerType.code == ctrl_code)
                .one_or_none()
            )
            if ctrl is None:
                errors.append(
                    f"Row {row_num}: controller_code {ctrl_code!r} is not a known controller type."
                )
                continue
            ctrl_id = ctrl.id

        existing = (
            session.query(EquipmentModel)
            .filter(
                EquipmentModel.manufacturer == manuf,
                EquipmentModel.model_code == code,
            )
            .one_or_none()
        )
        if existing is not None:
            existing.display_name = row.get("display_name", "").strip()
            existing.controller_type_id = ctrl_id
            existing.notes = row.get("notes", "").strip()
        else:
            create_equipment_model(
                session,
                manufacturer=manuf,
                model_code=code,
                display_name=row.get("display_name", "").strip(),
                controller_type_id=ctrl_id,
                notes=row.get("notes", "").strip(),
            )
        imported += 1
    return imported, errors


_EQUIPMENT_REQUIRED = {"client_name"}


def _resolve_client(session: Session, name: str) -> tuple[Client | None, str | None]:
    if not name:
        return None, "client_name is required."
    client = session.query(Client).filter(Client.name == name).one_or_none()
    if client is None:
        return None, f"client {name!r} not found — create it first."
    return client, None


def _resolve_location(
    session: Session, client: Client, label: str
) -> tuple[bytes | None, str | None]:
    if not label:
        return None, None
    loc = (
        session.query(Location)
        .filter(Location.client_id == client.id, Location.label == label)
        .one_or_none()
    )
    if loc is None:
        return None, (f"location {label!r} not found for client {client.name!r}.")
    return loc.id, None


def _resolve_model(
    session: Session, manuf: str, model_code: str
) -> tuple[bytes | None, str | None]:
    if not (manuf or model_code):
        return None, None
    if not (manuf and model_code):
        return None, "provide both manufacturer and model_code, or neither."
    mdl = (
        session.query(EquipmentModel)
        .filter(
            EquipmentModel.manufacturer == manuf,
            EquipmentModel.model_code == model_code,
        )
        .one_or_none()
    )
    if mdl is None:
        return None, f"equipment model {manuf} {model_code} not found."
    return mdl.id, None


def _resolve_controller(session: Session, code: str) -> tuple[bytes | None, str | None]:
    if not code:
        return None, None
    ctrl = (
        session.query(EquipmentControllerType)
        .filter(EquipmentControllerType.code == code)
        .one_or_none()
    )
    if ctrl is None:
        return None, f"controller_code {code!r} not found."
    return ctrl.id, None


def _parse_install_date(raw: str) -> tuple[date | None, str | None]:
    if not raw:
        return None, None
    try:
        return date.fromisoformat(raw), None
    except ValueError:
        return None, f"install_date {raw!r} is not ISO-formatted (YYYY-MM-DD)."


def _resolve_equipment_row(
    session: Session, row: dict[str, str]
) -> tuple[dict[str, Any] | None, str | None]:
    """Resolve every FK reference in ``row``; return create-kwargs or an error."""
    client, err = _resolve_client(session, row.get("client_name", "").strip())
    if err is not None or client is None:
        return None, err
    location_id, err = _resolve_location(session, client, row.get("location_label", "").strip())
    if err is not None:
        return None, err
    model_id, err = _resolve_model(
        session, row.get("manufacturer", "").strip(), row.get("model_code", "").strip()
    )
    if err is not None:
        return None, err
    ctrl_id, err = _resolve_controller(session, row.get("controller_code", "").strip())
    if err is not None:
        return None, err
    install_date, err = _parse_install_date(row.get("install_date", "").strip())
    if err is not None:
        return None, err
    return {
        "client_id": client.id,
        "location_id": location_id,
        "equipment_model_id": model_id,
        "controller_type_id": ctrl_id,
        "serial_number": row.get("serial_number", "").strip(),
        "asset_tag": row.get("asset_tag", "").strip(),
        "install_date": install_date,
        "notes": row.get("notes", "").strip(),
    }, None


def _import_equipment_row(session: Session, row: dict[str, str]) -> tuple[bool, str | None]:
    kwargs, err = _resolve_equipment_row(session, row)
    if err is not None or kwargs is None:
        return False, err
    # The resolvers above already verified the client / location / model /
    # controller exist and that the location belongs to the chosen client,
    # so ``create_equipment`` is guaranteed to succeed here.
    create_equipment(session, **kwargs)
    return True, None


def import_equipment_csv(session: Session, text: str) -> tuple[int, list[str]]:
    """Import equipment rows.

    Resolves client / location / model / controller by human-friendly
    fields (``client_name``, ``location_label``, ``manufacturer`` +
    ``model_code``, ``controller_code``) so the CSV file the user
    prepares doesn't need ULID hex strings.
    """
    reader, errors = _read_rows(text, _EQUIPMENT_REQUIRED)
    if errors:
        return 0, errors

    imported = 0
    for row_num, raw_row in enumerate(reader, start=2):
        row = {k.strip().lower(): v for k, v in raw_row.items() if k}
        ok, err = _import_equipment_row(session, row)
        if err is not None:
            errors.append(f"Row {row_num}: {err}")
        if ok:
            imported += 1
    return imported, errors
