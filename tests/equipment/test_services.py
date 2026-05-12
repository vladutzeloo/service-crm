"""Service-layer tests for the equipment blueprint."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.orm import Session

from service_crm.clients.models import Location
from service_crm.equipment import services
from service_crm.equipment.models import (
    Equipment,
    EquipmentControllerType,
    EquipmentModel,
    EquipmentWarranty,
)
from tests.factories import (
    ClientFactory,
    ControllerTypeFactory,
    EquipmentFactory,
    EquipmentModelFactory,
    EquipmentWarrantyFactory,
    LocationFactory,
)

# ── Controller types ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_controller_type(db_session: Session) -> None:
    ctrl = services.create_controller_type(
        db_session, code="FANUC-31i", name="Fanuc 31i", notes="Lathe controller"
    )
    assert ctrl.id is not None
    assert ctrl.code == "FANUC-31i"


@pytest.mark.integration
def test_update_controller_type(db_session: Session) -> None:
    ctrl = ControllerTypeFactory(code="SIEMENS-840D")
    db_session.flush()
    services.update_controller_type(
        db_session, ctrl, code="SIEMENS-840D", name="Siemens Sinumerik 840D"
    )
    assert ctrl.name == "Siemens Sinumerik 840D"


@pytest.mark.integration
def test_delete_controller_type(db_session: Session) -> None:
    ctrl = ControllerTypeFactory()
    db_session.flush()
    cid = ctrl.id
    services.delete_controller_type(db_session, ctrl)
    assert db_session.get(EquipmentControllerType, cid) is None


@pytest.mark.integration
def test_require_controller_type_invalid_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_controller_type(db_session, "not-hex")


@pytest.mark.integration
def test_require_controller_type_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="not found"):
        services.require_controller_type(db_session, ulid.new().hex())


# ── Equipment models ──────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_equipment_model(db_session: Session) -> None:
    ctrl = ControllerTypeFactory()
    db_session.flush()
    mdl = services.create_equipment_model(
        db_session,
        manufacturer="Mazak",
        model_code="VTC-300",
        display_name="Mazak VTC-300",
        controller_type_id=ctrl.id,
    )
    assert mdl.manufacturer == "Mazak"
    assert mdl.controller_type_id == ctrl.id


@pytest.mark.integration
def test_update_equipment_model(db_session: Session) -> None:
    mdl = EquipmentModelFactory(manufacturer="A", model_code="B")
    db_session.flush()
    services.update_equipment_model(
        db_session, mdl, manufacturer="A", model_code="B", display_name="A B Big"
    )
    assert mdl.display_name == "A B Big"


@pytest.mark.integration
def test_delete_equipment_model(db_session: Session) -> None:
    mdl = EquipmentModelFactory()
    db_session.flush()
    mid = mdl.id
    services.delete_equipment_model(db_session, mdl)
    assert db_session.get(EquipmentModel, mid) is None


@pytest.mark.integration
def test_require_equipment_model_invalid_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_equipment_model(db_session, "not-hex")


@pytest.mark.integration
def test_require_equipment_model_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="not found"):
        services.require_equipment_model(db_session, ulid.new().hex())


@pytest.mark.integration
def test_list_equipment_models_order(db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="Z", model_code="ZZ")
    EquipmentModelFactory(manufacturer="A", model_code="AA")
    db_session.flush()
    items = services.list_equipment_models(db_session)
    names = [m.manufacturer for m in items]
    assert names.index("A") < names.index("Z")


# ── Equipment ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_equipment_minimal(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    eq = services.create_equipment(
        db_session,
        client_id=client.id,
        serial_number="  SN-1  ",
        asset_tag="  AT-1  ",
    )
    assert eq.id is not None
    assert eq.serial_number == "SN-1"
    assert eq.asset_tag == "AT-1"
    assert eq.is_active is True


@pytest.mark.integration
def test_create_equipment_missing_client(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="client not found"):
        services.create_equipment(db_session, client_id=ulid.new())


@pytest.mark.integration
def test_create_equipment_location_must_belong_to_client(db_session: Session) -> None:
    """The core 0.4.0 constraint: rejecting cross-client location assignments."""
    client_a = ClientFactory()
    client_b = ClientFactory()
    loc_of_b = LocationFactory(client=client_b)
    db_session.flush()

    with pytest.raises(ValueError, match="location does not belong"):
        services.create_equipment(db_session, client_id=client_a.id, location_id=loc_of_b.id)


@pytest.mark.integration
def test_create_equipment_location_unknown(db_session: Session) -> None:
    from service_crm.shared import ulid

    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="location not found"):
        services.create_equipment(db_session, client_id=client.id, location_id=ulid.new())


@pytest.mark.integration
def test_create_equipment_with_matching_location(db_session: Session) -> None:
    client = ClientFactory()
    loc = LocationFactory(client=client)
    db_session.flush()
    eq = services.create_equipment(db_session, client_id=client.id, location_id=loc.id)
    assert eq.location_id == loc.id


@pytest.mark.integration
def test_update_equipment_missing_client(db_session: Session) -> None:
    from service_crm.shared import ulid

    eq = EquipmentFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="client not found"):
        services.update_equipment(db_session, eq, client_id=ulid.new())


@pytest.mark.integration
def test_update_equipment_rejects_foreign_location(db_session: Session) -> None:
    eq = EquipmentFactory()
    other = ClientFactory()
    foreign_loc = LocationFactory(client=other)
    db_session.flush()
    with pytest.raises(ValueError, match="location does not belong"):
        services.update_equipment(
            db_session,
            eq,
            client_id=eq.client_id,
            location_id=foreign_loc.id,
        )


@pytest.mark.integration
def test_update_equipment_strips_and_persists(db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    services.update_equipment(
        db_session,
        eq,
        client_id=eq.client_id,
        serial_number="  S2  ",
        asset_tag="  T2  ",
        install_date=date(2026, 3, 1),
        notes="  hello  ",
    )
    assert eq.serial_number == "S2"
    assert eq.asset_tag == "T2"
    assert eq.install_date == date(2026, 3, 1)
    assert eq.notes == "hello"


@pytest.mark.integration
def test_deactivate_reactivate_equipment(db_session: Session) -> None:
    eq = EquipmentFactory(is_active=True)
    db_session.flush()
    services.deactivate_equipment(db_session, eq)
    assert eq.is_active is False
    services.reactivate_equipment(db_session, eq)
    assert eq.is_active is True


@pytest.mark.integration
def test_list_equipment_active_only_by_default(db_session: Session) -> None:
    EquipmentFactory(asset_tag="ACTIVE-EQ", is_active=True)
    EquipmentFactory(asset_tag="INACTIVE-EQ", is_active=False)
    db_session.flush()
    items, _total = services.list_equipment(db_session)
    tags = [e.asset_tag for e in items]
    assert "ACTIVE-EQ" in tags
    assert "INACTIVE-EQ" not in tags


@pytest.mark.integration
def test_list_equipment_includes_inactive_when_asked(db_session: Session) -> None:
    EquipmentFactory(asset_tag="ACT2", is_active=True)
    EquipmentFactory(asset_tag="INACT2", is_active=False)
    db_session.flush()
    items, _ = services.list_equipment(db_session, active_only=False)
    tags = [e.asset_tag for e in items]
    assert "ACT2" in tags
    assert "INACT2" in tags


@pytest.mark.integration
def test_list_equipment_filter_by_client(db_session: Session) -> None:
    client_a = ClientFactory()
    client_b = ClientFactory()
    EquipmentFactory(client=client_a, asset_tag="A-eq")
    EquipmentFactory(client=client_b, asset_tag="B-eq")
    db_session.flush()
    items, _ = services.list_equipment(db_session, client_id=client_a.id)
    tags = [e.asset_tag for e in items]
    assert tags == ["A-eq"]


@pytest.mark.integration
def test_list_equipment_search_serial(db_session: Session) -> None:
    EquipmentFactory(serial_number="UNIQUE-SN-XYZ")
    EquipmentFactory(serial_number="OTHER")
    db_session.flush()
    items, _ = services.list_equipment(db_session, q="UNIQUE-SN-XYZ")
    assert len(items) == 1
    assert items[0].serial_number == "UNIQUE-SN-XYZ"


@pytest.mark.integration
def test_list_equipment_search_asset_tag(db_session: Session) -> None:
    EquipmentFactory(asset_tag="UNIQUE-TAG-XYZ")
    EquipmentFactory(asset_tag="OTHER")
    db_session.flush()
    items, _ = services.list_equipment(db_session, q="UNIQUE-TAG-XYZ")
    assert len(items) == 1


@pytest.mark.integration
def test_equipment_search_filter_postgres_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("service_crm.equipment.services._dialect", lambda: "postgresql")
    flt = services._equipment_search_filter("xyz")
    assert flt is not None


@pytest.mark.integration
def test_equipment_search_filter_sqlite_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Exercise the LIKE fallback even when running against Postgres so
    coverage doesn't dip on the dual-DB CI matrix."""
    monkeypatch.setattr("service_crm.equipment.services._dialect", lambda: "sqlite")
    flt = services._equipment_search_filter("xyz")
    assert flt is not None


@pytest.mark.integration
def test_equipment_search_filter_empty_returns_none(db_session: Session) -> None:
    assert services._equipment_search_filter("   ") is None


@pytest.mark.integration
def test_require_equipment_invalid_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_equipment(db_session, "not-hex")


@pytest.mark.integration
def test_require_equipment_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="not found"):
        services.require_equipment(db_session, ulid.new().hex())


# ── Warranties ────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_warranty(db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    w = services.create_warranty(
        db_session,
        equipment_id=eq.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
        reference="W1",
    )
    assert w.id is not None
    assert w.equipment_id == eq.id


@pytest.mark.integration
def test_create_warranty_rejects_bad_dates(db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ends_on must be after"):
        services.create_warranty(
            db_session,
            equipment_id=eq.id,
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 5, 1),
        )


@pytest.mark.integration
def test_update_warranty(db_session: Session) -> None:
    w = EquipmentWarrantyFactory(
        starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1), reference="OLD"
    )
    db_session.flush()
    services.update_warranty(
        db_session,
        w,
        starts_on=date(2026, 2, 1),
        ends_on=date(2027, 2, 1),
        reference="NEW",
    )
    assert w.reference == "NEW"
    assert w.starts_on == date(2026, 2, 1)


@pytest.mark.integration
def test_update_warranty_rejects_bad_dates(db_session: Session) -> None:
    w = EquipmentWarrantyFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ends_on must be after"):
        services.update_warranty(
            db_session,
            w,
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 5, 1),
        )


@pytest.mark.integration
def test_delete_warranty(db_session: Session) -> None:
    w = EquipmentWarrantyFactory()
    db_session.flush()
    wid = w.id
    services.delete_warranty(db_session, w)
    assert db_session.get(EquipmentWarranty, wid) is None


@pytest.mark.integration
def test_require_warranty_wrong_equipment(db_session: Session) -> None:
    """Warranty IDs from a different equipment row must not resolve."""
    eq1 = EquipmentFactory()
    eq2 = EquipmentFactory()
    w = EquipmentWarrantyFactory(equipment=eq1)
    db_session.flush()
    with pytest.raises(ValueError, match="warranty not found"):
        services.require_warranty(db_session, w.id.hex(), eq2)


@pytest.mark.integration
def test_require_warranty_invalid_hex(db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="invalid"):
        services.require_warranty(db_session, "not-hex", eq)


# ── CSV imports ───────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_import_controller_types_csv(db_session: Session) -> None:
    csv = "code,name,notes\nFANUC-31i,Fanuc 31i,Lathe\nSIEMENS-840D,Siemens 840D,Mill\n"
    imported, errors = services.import_controller_types_csv(db_session, csv)
    db_session.flush()
    assert imported == 2
    assert errors == []
    assert (
        db_session.query(EquipmentControllerType)
        .filter(EquipmentControllerType.code == "FANUC-31i")
        .count()
        == 1
    )


@pytest.mark.integration
def test_import_controller_types_csv_updates_existing(db_session: Session) -> None:
    ControllerTypeFactory(code="FANUC-31i", name="Fanuc 31i (old)")
    db_session.flush()
    csv = "code,name\nFANUC-31i,Fanuc 31i (updated)\n"
    imported, errors = services.import_controller_types_csv(db_session, csv)
    db_session.flush()
    assert imported == 1
    assert errors == []
    refreshed = (
        db_session.query(EquipmentControllerType)
        .filter(EquipmentControllerType.code == "FANUC-31i")
        .one()
    )
    assert refreshed.name == "Fanuc 31i (updated)"


@pytest.mark.integration
def test_import_controller_types_csv_empty(db_session: Session) -> None:
    imported, errors = services.import_controller_types_csv(db_session, "")
    assert imported == 0
    assert errors and "empty" in errors[0]


@pytest.mark.integration
def test_import_controller_types_missing_columns(db_session: Session) -> None:
    imported, errors = services.import_controller_types_csv(db_session, "code\nABC\n")
    assert imported == 0
    assert any("Missing required" in e for e in errors)


@pytest.mark.integration
def test_import_controller_types_blank_row(db_session: Session) -> None:
    imported, errors = services.import_controller_types_csv(db_session, "code,name\n,Bad\n")
    assert imported == 0
    assert any("required" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_models_csv(db_session: Session) -> None:
    ControllerTypeFactory(code="FANUC-31i")
    db_session.flush()
    csv = (
        "manufacturer,model_code,display_name,controller_code,notes\n"
        "Mazak,VTC-300,Mazak VTC-300,FANUC-31i,Five-axis mill\n"
    )
    imported, errors = services.import_equipment_models_csv(db_session, csv)
    db_session.flush()
    assert imported == 1
    assert errors == []
    mdl = db_session.query(EquipmentModel).filter(EquipmentModel.manufacturer == "Mazak").one()
    assert mdl.controller_type_id is not None


@pytest.mark.integration
def test_import_equipment_models_updates(db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-300", display_name="old")
    db_session.flush()
    csv = "manufacturer,model_code,display_name\nMazak,VTC-300,new name\n"
    imported, errors = services.import_equipment_models_csv(db_session, csv)
    db_session.flush()
    assert imported == 1
    assert errors == []
    refreshed = (
        db_session.query(EquipmentModel).filter(EquipmentModel.manufacturer == "Mazak").one()
    )
    assert refreshed.display_name == "new name"


@pytest.mark.integration
def test_import_equipment_models_unknown_controller(db_session: Session) -> None:
    csv = "manufacturer,model_code,controller_code\nA,B,UNKNOWN-CODE\n"
    imported, errors = services.import_equipment_models_csv(db_session, csv)
    assert imported == 0
    assert any("controller_code" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_models_missing_required(db_session: Session) -> None:
    imported, errors = services.import_equipment_models_csv(db_session, "manufacturer\nMazak\n")
    assert imported == 0
    assert any("Missing required" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_models_blank_row(db_session: Session) -> None:
    imported, errors = services.import_equipment_models_csv(
        db_session, "manufacturer,model_code\n,B\n"
    )
    assert imported == 0
    assert any("required" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_minimal(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,serial_number,asset_tag\nAcme,SN-1,AT-1\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    db_session.flush()
    assert imported == 1
    assert errors == []
    eq = db_session.query(Equipment).filter(Equipment.serial_number == "SN-1").one()
    assert eq.asset_tag == "AT-1"


@pytest.mark.integration
def test_import_equipment_csv_full_row(db_session: Session) -> None:
    client = ClientFactory(name="Acme")
    loc = LocationFactory(client=client, label="HQ")
    ctrl = ControllerTypeFactory(code="FANUC-31i")
    EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-300")
    db_session.flush()
    csv = (
        "client_name,location_label,manufacturer,model_code,controller_code,"
        "serial_number,asset_tag,install_date,notes\n"
        "Acme,HQ,Mazak,VTC-300,FANUC-31i,SN-7,AT-7,2026-02-15,green\n"
    )
    imported, errors = services.import_equipment_csv(db_session, csv)
    db_session.flush()
    assert imported == 1, errors
    assert errors == []
    eq = db_session.query(Equipment).filter(Equipment.serial_number == "SN-7").one()
    assert eq.location_id == loc.id
    assert eq.controller_type_id == ctrl.id
    assert eq.install_date == date(2026, 2, 15)


@pytest.mark.integration
def test_import_equipment_csv_unknown_client(db_session: Session) -> None:
    csv = "client_name\nNoSuch\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("not found" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_unknown_location(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,location_label\nAcme,Nowhere\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("location" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_bad_install_date(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,install_date\nAcme,not-a-date\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("install_date" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_partial_model_fields(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,manufacturer\nAcme,Mazak\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("manufacturer and model_code" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_unknown_model(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,manufacturer,model_code\nAcme,UnknownCorp,X9\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("equipment model" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_unknown_controller(db_session: Session) -> None:
    ClientFactory(name="Acme")
    db_session.flush()
    csv = "client_name,controller_code\nAcme,UNKNOWN\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("controller_code" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_missing_client_name(db_session: Session) -> None:
    csv = "client_name,serial_number\n,SN-blank\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("client_name is required" in e for e in errors)


@pytest.mark.integration
def test_import_equipment_csv_missing_required_column(db_session: Session) -> None:
    csv = "serial_number\nSN-1\n"
    imported, errors = services.import_equipment_csv(db_session, csv)
    assert imported == 0
    assert any("Missing required" in e for e in errors)


@pytest.mark.integration
def test_location_cascade_via_client_delete_removes_equipment_location_first(
    db_session: Session,
) -> None:
    """Sanity-check Location FK behaves: SET NULL when the location is gone."""
    client = ClientFactory()
    loc = LocationFactory(client=client)
    eq = EquipmentFactory(client=client, location=loc)
    db_session.flush()
    db_session.delete(loc)
    db_session.flush()
    db_session.refresh(eq)
    assert eq.location_id is None
    # The Location row is gone.
    assert db_session.query(Location).filter(Location.id == loc.id).count() == 0
