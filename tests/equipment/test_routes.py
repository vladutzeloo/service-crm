"""E2E tests for the equipment blueprint routes.

Authenticated via ``client_logged_in``; DB assertions go through
``db_session`` (same SAVEPOINT as the request)."""

from __future__ import annotations

import io
from datetime import date

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

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

# ── List ──────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_list_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/equipment/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.mark.e2e
def test_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    EquipmentFactory(asset_tag="VISIBLE-ASSET-XYZ")
    db_session.flush()
    resp = client_logged_in.get("/equipment/")
    assert resp.status_code == 200
    assert b"VISIBLE-ASSET-XYZ" in resp.data


@pytest.mark.e2e
def test_list_filters_by_client(client_logged_in: FlaskClient, db_session: Session) -> None:
    c_a = ClientFactory(name="ClientA")
    c_b = ClientFactory(name="ClientB")
    EquipmentFactory(client=c_a, asset_tag="A-Only-Asset")
    EquipmentFactory(client=c_b, asset_tag="B-Only-Asset")
    db_session.flush()
    resp = client_logged_in.get(f"/equipment/?client={c_a.id.hex()}")
    assert resp.status_code == 200
    assert b"A-Only-Asset" in resp.data
    assert b"B-Only-Asset" not in resp.data


@pytest.mark.e2e
def test_list_search_filters(client_logged_in: FlaskClient, db_session: Session) -> None:
    EquipmentFactory(serial_number="UNIQUE-SN-MARKER")
    EquipmentFactory(serial_number="OTHER-SN")
    db_session.flush()
    resp = client_logged_in.get("/equipment/?q=UNIQUE-SN-MARKER")
    assert b"UNIQUE-SN-MARKER" in resp.data
    assert b"OTHER-SN" not in resp.data


@pytest.mark.e2e
def test_list_show_all_includes_inactive(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    EquipmentFactory(asset_tag="ACT", is_active=True)
    EquipmentFactory(asset_tag="INACT", is_active=False)
    db_session.flush()
    active_only = client_logged_in.get("/equipment/")
    assert b"INACT" not in active_only.data
    show_all = client_logged_in.get("/equipment/?show=all")
    assert b"INACT" in show_all.data


@pytest.mark.e2e
def test_list_bad_client_hex_ignored(client_logged_in: FlaskClient, db_session: Session) -> None:
    EquipmentFactory(asset_tag="VISIBLE-Q")
    db_session.flush()
    resp = client_logged_in.get("/equipment/?client=not-hex")
    assert resp.status_code == 200
    assert b"VISIBLE-Q" in resp.data


# ── New / Edit ────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_new_get_renders_form(client_logged_in: FlaskClient, db_session: Session) -> None:
    ClientFactory(name="Form Client")
    db_session.flush()
    resp = client_logged_in.get("/equipment/new")
    assert resp.status_code == 200
    assert b"Form Client" in resp.data
    assert b'name="client_id"' in resp.data


@pytest.mark.e2e
def test_new_get_with_preselected_client(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    client = ClientFactory(name="Preselected")
    db_session.flush()
    resp = client_logged_in.get(f"/equipment/new?client={client.id.hex()}")
    assert resp.status_code == 200
    assert client.id.hex().encode() in resp.data


@pytest.mark.e2e
def test_new_post_creates(client_logged_in: FlaskClient, db_session: Session) -> None:
    client = ClientFactory(name="Buyer")
    db_session.flush()
    resp = client_logged_in.post(
        "/equipment/new",
        data={
            "client_id": client.id.hex(),
            "location_id": "",
            "equipment_model_id": "",
            "controller_type_id": "",
            "serial_number": "SN-CREATED",
            "asset_tag": "AT-CREATED",
            "install_date": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Equipment).filter(Equipment.serial_number == "SN-CREATED").count() == 1


@pytest.mark.e2e
def test_new_post_no_client_stays_on_form(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    resp = client_logged_in.post(
        "/equipment/new",
        data={
            "client_id": "",
            "location_id": "",
            "equipment_model_id": "",
            "controller_type_id": "",
            "serial_number": "",
            "asset_tag": "",
            "install_date": "",
            "notes": "",
        },
    )
    assert resp.status_code == 200
    assert b"<form" in resp.data


@pytest.mark.e2e
def test_new_post_foreign_location_flashes_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    client_a = ClientFactory(name="A")
    client_b = ClientFactory(name="B")
    loc_b = LocationFactory(client=client_b, label="HQ-B")
    db_session.flush()
    resp = client_logged_in.post(
        "/equipment/new",
        data={
            "client_id": client_a.id.hex(),
            "location_id": loc_b.id.hex(),
            "equipment_model_id": "",
            "controller_type_id": "",
            "serial_number": "SN-1",
            "asset_tag": "AT-1",
            "install_date": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert b"location does not belong" in resp.data


@pytest.mark.e2e
def test_edit_get_renders_form(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="EDIT-AT")
    db_session.flush()
    resp = client_logged_in.get(f"/equipment/{eq.id.hex()}/edit")
    assert resp.status_code == 200
    assert b"EDIT-AT" in resp.data


@pytest.mark.e2e
def test_edit_post_updates(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="OLD")
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/edit",
        data={
            "client_id": eq.client_id.hex(),
            "location_id": "",
            "equipment_model_id": "",
            "controller_type_id": "",
            "serial_number": eq.serial_number,
            "asset_tag": "NEW",
            "install_date": "",
            "notes": "after",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(eq)
    assert eq.asset_tag == "NEW"
    assert eq.notes == "after"


@pytest.mark.e2e
def test_edit_unknown_redirects(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.get(f"/equipment/{ulid.new().hex()}/edit", follow_redirects=False)
    assert resp.status_code == 302
    assert "/equipment" in resp.headers["Location"]


@pytest.mark.e2e
def test_edit_post_foreign_location_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    eq = EquipmentFactory(asset_tag="EDIT-FL")
    other_client = ClientFactory(name="OtherClient")
    foreign_loc = LocationFactory(client=other_client, label="Foreign")
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/edit",
        data={
            "client_id": eq.client_id.hex(),
            "location_id": foreign_loc.id.hex(),
            "equipment_model_id": "",
            "controller_type_id": "",
            "serial_number": eq.serial_number,
            "asset_tag": "EDIT-FL",
            "install_date": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert b"location does not belong" in resp.data


# ── Detail ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="DETAIL-AT")
    db_session.flush()
    resp = client_logged_in.get(f"/equipment/{eq.id.hex()}")
    assert resp.status_code == 200
    assert b"DETAIL-AT" in resp.data
    assert b"Warranties" in resp.data or b"Garan" in resp.data


@pytest.mark.e2e
def test_detail_missing_redirects(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.get(f"/equipment/{ulid.new().hex()}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_detail_unknown_edit_warranty_falls_through(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/equipment/{eq.id.hex()}?tab=warranties&edit_warranty=not-hex")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_detail_edit_warranty_pre_fills(client_logged_in: FlaskClient, db_session: Session) -> None:
    """Opening the detail page with ?edit_warranty=<hex> pre-fills the
    edit form via WTForms ``obj=``."""
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(
        equipment=eq,
        reference="PRE-FILL-XYZ",
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )
    db_session.flush()
    resp = client_logged_in.get(
        f"/equipment/{eq.id.hex()}?tab=warranties&edit_warranty={w.id.hex()}"
    )
    assert resp.status_code == 200
    assert b"PRE-FILL-XYZ" in resp.data


# ── Activate / Deactivate ─────────────────────────────────────────────────────


@pytest.mark.e2e
def test_deactivate_reactivate(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory(is_active=True)
    db_session.flush()
    client_logged_in.post(f"/equipment/{eq.id.hex()}/deactivate")
    db_session.refresh(eq)
    assert eq.is_active is False
    client_logged_in.post(f"/equipment/{eq.id.hex()}/reactivate")
    db_session.refresh(eq)
    assert eq.is_active is True


@pytest.mark.e2e
def test_deactivate_unknown(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/{ulid.new().hex()}/deactivate", follow_redirects=False
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_reactivate_unknown(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/{ulid.new().hex()}/reactivate", follow_redirects=False
    )
    assert resp.status_code == 302


# ── Warranties ────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_warranty_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties",
        data={
            "warranty-reference": "WX",
            "warranty-provider": "Vendor",
            "warranty-starts_on": "2026-01-01",
            "warranty-ends_on": "2027-01-01",
            "warranty-notes": "",
        },
    )
    assert (
        db_session.query(EquipmentWarranty).filter(EquipmentWarranty.equipment_id == eq.id).count()
        == 1
    )


@pytest.mark.e2e
def test_warranty_create_bad_dates(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties",
        data={
            "warranty-reference": "BAD",
            "warranty-starts_on": "2026-06-01",
            "warranty-ends_on": "2026-05-01",
        },
        follow_redirects=True,
    )
    assert b"ends_on must be after" in resp.data
    assert (
        db_session.query(EquipmentWarranty).filter(EquipmentWarranty.equipment_id == eq.id).count()
        == 0
    )


@pytest.mark.e2e
def test_warranty_create_missing_dates(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties",
        data={"warranty-reference": "X"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert (
        db_session.query(EquipmentWarranty).filter(EquipmentWarranty.equipment_id == eq.id).count()
        == 0
    )


@pytest.mark.e2e
def test_warranty_create_unknown_equipment(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/{ulid.new().hex()}/warranties",
        data={
            "warranty-starts_on": "2026-01-01",
            "warranty-ends_on": "2027-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_warranty_update(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(
        equipment=eq,
        reference="OLD",
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )
    db_session.flush()
    client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties/{w.id.hex()}",
        data={
            "warranty-reference": "RENAMED",
            "warranty-provider": "",
            "warranty-starts_on": "2026-01-01",
            "warranty-ends_on": "2028-01-01",
            "warranty-notes": "",
        },
    )
    db_session.refresh(w)
    assert w.reference == "RENAMED"
    assert w.ends_on == date(2028, 1, 1)


@pytest.mark.e2e
def test_warranty_update_unknown_warranty(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    from service_crm.shared import ulid

    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties/{ulid.new().hex()}",
        data={
            "warranty-starts_on": "2026-01-01",
            "warranty-ends_on": "2027-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_warranty_update_unknown_equipment(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/{ulid.new().hex()}/warranties/{ulid.new().hex()}",
        data={
            "warranty-starts_on": "2026-01-01",
            "warranty-ends_on": "2027-01-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_warranty_update_bad_dates_redirects_to_edit(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(equipment=eq, starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1))
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties/{w.id.hex()}",
        data={
            "warranty-starts_on": "2026-06-01",
            "warranty-ends_on": "2026-05-01",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "edit_warranty=" in resp.headers["Location"]


@pytest.mark.e2e
def test_warranty_update_invalid_form(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(equipment=eq)
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties/{w.id.hex()}",
        data={"warranty-reference": "no-dates"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "edit_warranty=" in resp.headers["Location"]


@pytest.mark.e2e
def test_warranty_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(equipment=eq)
    db_session.flush()
    wid = w.id
    client_logged_in.post(f"/equipment/{eq.id.hex()}/warranties/{wid.hex()}/delete")
    assert db_session.get(EquipmentWarranty, wid) is None


@pytest.mark.e2e
def test_warranty_delete_unknown(client_logged_in: FlaskClient, db_session: Session) -> None:
    from service_crm.shared import ulid

    eq = EquipmentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/equipment/{eq.id.hex()}/warranties/{ulid.new().hex()}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_warranty_delete_unknown_equipment(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/{ulid.new().hex()}/warranties/{ulid.new().hex()}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Controller-type lookup ────────────────────────────────────────────────────


@pytest.mark.e2e
def test_controllers_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ControllerTypeFactory(code="SHOW-CT", name="Show CT")
    db_session.flush()
    resp = client_logged_in.get("/equipment/controllers")
    assert resp.status_code == 200
    assert b"SHOW-CT" in resp.data


@pytest.mark.e2e
def test_controller_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.post(
        "/equipment/controllers/new",
        data={"code": "NEW-CTRL", "name": "New Controller", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(EquipmentControllerType)
        .filter(EquipmentControllerType.code == "NEW-CTRL")
        .count()
        == 1
    )


@pytest.mark.e2e
def test_controller_create_duplicate_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    ControllerTypeFactory(code="ROUTE-DUPE-CTRL")
    db_session.flush()
    resp = client_logged_in.post(
        "/equipment/controllers/new",
        data={"code": "ROUTE-DUPE-CTRL", "name": "Dupe", "notes": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_controller_create_invalid_flashes(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.post(
        "/equipment/controllers/new",
        data={"code": "", "name": "", "notes": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_controller_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    ctrl = ControllerTypeFactory()
    db_session.flush()
    cid = ctrl.id
    client_logged_in.post(f"/equipment/controllers/{cid.hex()}/delete")
    assert db_session.get(EquipmentControllerType, cid) is None


@pytest.mark.e2e
def test_controller_delete_unknown(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/controllers/{ulid.new().hex()}/delete", follow_redirects=False
    )
    assert resp.status_code == 302


# ── Equipment-model lookup ────────────────────────────────────────────────────


@pytest.mark.e2e
def test_models_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-XYZ-show")
    db_session.flush()
    resp = client_logged_in.get("/equipment/models")
    assert resp.status_code == 200
    assert b"VTC-XYZ-show" in resp.data


@pytest.mark.e2e
def test_model_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.post(
        "/equipment/models/new",
        data={
            "manufacturer": "RouteMazak",
            "model_code": "ROUTE-VTC-300",
            "display_name": "",
            "controller_type_id": "",
            "notes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(EquipmentModel).filter(EquipmentModel.manufacturer == "RouteMazak").count()
        == 1
    )


@pytest.mark.e2e
def test_model_create_duplicate(client_logged_in: FlaskClient, db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="RouteDup", model_code="ROUTE-DUP-1")
    db_session.flush()
    resp = client_logged_in.post(
        "/equipment/models/new",
        data={
            "manufacturer": "RouteDup",
            "model_code": "ROUTE-DUP-1",
            "display_name": "",
            "controller_type_id": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_model_create_invalid_form(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/equipment/models/new",
        data={
            "manufacturer": "",
            "model_code": "",
            "display_name": "",
            "controller_type_id": "",
            "notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_model_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    mdl = EquipmentModelFactory()
    db_session.flush()
    mid = mdl.id
    client_logged_in.post(f"/equipment/models/{mid.hex()}/delete")
    assert db_session.get(EquipmentModel, mid) is None


@pytest.mark.e2e
def test_model_delete_unknown(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.post(
        f"/equipment/models/{ulid.new().hex()}/delete", follow_redirects=False
    )
    assert resp.status_code == 302


# ── CSV imports ───────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_import_equipment_get_renders(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/equipment/import")
    assert resp.status_code == 200
    assert b"client_name" in resp.data


@pytest.mark.e2e
def test_import_equipment_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    ClientFactory(name="Importer Co")
    db_session.flush()
    data = "client_name,serial_number,asset_tag\nImporter Co,IMP-1,IMP-T\n"
    resp = client_logged_in.post(
        "/equipment/import",
        data={"csv_file": (io.BytesIO(data.encode()), "import.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Equipment).filter(Equipment.serial_number == "IMP-1").count() == 1


@pytest.mark.e2e
def test_import_equipment_post_errors(client_logged_in: FlaskClient, db_session: Session) -> None:
    """Errors keep us on the form with a flashed message."""
    data = "client_name\nNoSuch\n"
    resp = client_logged_in.post(
        "/equipment/import",
        data={"csv_file": (io.BytesIO(data.encode()), "x.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"not found" in resp.data


@pytest.mark.e2e
def test_import_controllers_get_renders(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/equipment/controllers/import")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_import_controllers_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    data = "code,name\nIMP-CTRL,Imported Controller\n"
    resp = client_logged_in.post(
        "/equipment/controllers/import",
        data={"csv_file": (io.BytesIO(data.encode()), "ctrl.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(EquipmentControllerType)
        .filter(EquipmentControllerType.code == "IMP-CTRL")
        .count()
        == 1
    )


@pytest.mark.e2e
def test_import_controllers_post_errors(client_logged_in: FlaskClient) -> None:
    data = "code\nMissingName\n"
    resp = client_logged_in.post(
        "/equipment/controllers/import",
        data={"csv_file": (io.BytesIO(data.encode()), "ctrl.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Missing required" in resp.data


@pytest.mark.e2e
def test_import_models_get_renders(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/equipment/models/import")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_import_models_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    data = "manufacturer,model_code,display_name\nImpMaker,IMP-100,Imported\n"
    resp = client_logged_in.post(
        "/equipment/models/import",
        data={"csv_file": (io.BytesIO(data.encode()), "models.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(EquipmentModel).filter(EquipmentModel.manufacturer == "ImpMaker").count()
        == 1
    )


@pytest.mark.e2e
def test_import_models_post_errors(client_logged_in: FlaskClient) -> None:
    data = "manufacturer\nIncomplete\n"
    resp = client_logged_in.post(
        "/equipment/models/import",
        data={"csv_file": (io.BytesIO(data.encode()), "models.csv")},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"Missing required" in resp.data
