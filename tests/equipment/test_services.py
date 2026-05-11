"""Service-layer integration tests for the equipment blueprint."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from service_crm.equipment import services
from service_crm.equipment.models import EquipmentWarranty
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    EquipmentModelFactory,
    LocationFactory,
)

# ── Equipment CRUD ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_equipment_minimal(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()

    equip = services.create_equipment(db_session, client_id=client.id, name="  CNC-01  ")

    assert equip.id is not None
    assert equip.name == "CNC-01"
    assert equip.is_active is True
    assert equip.client_id == client.id


@pytest.mark.integration
def test_create_equipment_with_location(db_session: Session) -> None:
    client = ClientFactory()
    loc = LocationFactory(client=client)
    db_session.flush()

    equip = services.create_equipment(
        db_session, client_id=client.id, name="CNC-02", location_id=loc.id
    )

    assert equip.location_id == loc.id


@pytest.mark.integration
def test_create_equipment_rejects_wrong_client_location(db_session: Session) -> None:
    """location_id from a different client is rejected."""
    client_a = ClientFactory()
    client_b = ClientFactory()
    loc_b = LocationFactory(client=client_b)
    db_session.flush()

    with pytest.raises(ValueError, match="same client"):
        services.create_equipment(
            db_session, client_id=client_a.id, name="Bad", location_id=loc_b.id
        )


@pytest.mark.integration
def test_create_equipment_rejects_unknown_location(db_session: Session) -> None:
    from service_crm.shared import ulid

    client = ClientFactory()
    db_session.flush()

    with pytest.raises(ValueError, match="same client"):
        services.create_equipment(
            db_session, client_id=client.id, name="Bad", location_id=ulid.new()
        )


@pytest.mark.integration
def test_update_equipment(db_session: Session) -> None:
    equip = EquipmentFactory(name="Old Name")
    db_session.flush()

    services.update_equipment(
        db_session,
        equip,
        name="New Name",
        manufacturer="Mazak",
        model="VTC-800",
    )

    assert equip.name == "New Name"
    assert equip.manufacturer == "Mazak"


@pytest.mark.integration
def test_update_equipment_rejects_wrong_client_location(db_session: Session) -> None:
    client_a = ClientFactory()
    client_b = ClientFactory()
    loc_b = LocationFactory(client=client_b)
    equip = EquipmentFactory(_client=client_a)
    db_session.flush()

    with pytest.raises(ValueError, match="same client"):
        services.update_equipment(db_session, equip, name="X", location_id=loc_b.id)


@pytest.mark.integration
def test_deactivate_and_reactivate(db_session: Session) -> None:
    equip = EquipmentFactory(is_active=True)
    db_session.flush()

    services.deactivate_equipment(db_session, equip)
    assert equip.is_active is False

    services.reactivate_equipment(db_session, equip)
    assert equip.is_active is True


@pytest.mark.integration
def test_get_equipment_returns_none_for_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    assert services.get_equipment(db_session, ulid.new()) is None


@pytest.mark.integration
def test_get_equipment_returns_existing(db_session: Session) -> None:
    equip = EquipmentFactory()
    db_session.flush()

    assert services.get_equipment(db_session, equip.id) is equip


@pytest.mark.integration
def test_require_equipment_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_equipment(db_session, "not-hex")


@pytest.mark.integration
def test_require_equipment_not_found(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="not found"):
        services.require_equipment(db_session, ulid.new().hex())


@pytest.mark.integration
def test_list_equipment_active_only(db_session: Session) -> None:
    client = ClientFactory()
    EquipmentFactory(_client=client, name="Active", is_active=True)
    EquipmentFactory(_client=client, name="Inactive", is_active=False)
    db_session.flush()

    items, total = services.list_equipment(db_session, client_id=client.id)

    names = [e.name for e in items]
    assert "Active" in names
    assert "Inactive" not in names
    assert total == 1


@pytest.mark.integration
def test_list_equipment_includes_inactive(db_session: Session) -> None:
    client = ClientFactory()
    EquipmentFactory(_client=client, name="Active2", is_active=True)
    EquipmentFactory(_client=client, name="Inactive2", is_active=False)
    db_session.flush()

    items, total = services.list_equipment(db_session, client_id=client.id, active_only=False)

    names = [e.name for e in items]
    assert "Active2" in names
    assert "Inactive2" in names
    assert total == 2


# ── Warranties ────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_warranty_happy_path(db_session: Session) -> None:
    from datetime import date

    equip = EquipmentFactory()
    db_session.flush()

    w = services.create_warranty(
        db_session,
        equipment_id=equip.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
        coverage="Full parts + labour",
    )

    assert w.id is not None
    assert w.coverage == "Full parts + labour"


@pytest.mark.integration
def test_create_warranty_rejects_bad_dates(db_session: Session) -> None:
    from datetime import date

    equip = EquipmentFactory()
    db_session.flush()

    with pytest.raises(ValueError, match="ends_on"):
        services.create_warranty(
            db_session,
            equipment_id=equip.id,
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 5, 1),
        )


@pytest.mark.integration
def test_update_warranty(db_session: Session) -> None:
    from datetime import date

    equip = EquipmentFactory()
    db_session.flush()
    w = services.create_warranty(
        db_session,
        equipment_id=equip.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )

    services.update_warranty(
        db_session, w, starts_on=date(2026, 3, 1), ends_on=date(2028, 3, 1), coverage="Parts"
    )

    assert w.coverage == "Parts"
    assert w.ends_on == date(2028, 3, 1)


@pytest.mark.integration
def test_update_warranty_rejects_bad_dates(db_session: Session) -> None:
    from datetime import date

    equip = EquipmentFactory()
    db_session.flush()
    w = services.create_warranty(
        db_session,
        equipment_id=equip.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )

    with pytest.raises(ValueError, match="ends_on"):
        services.update_warranty(
            db_session, w, starts_on=date(2026, 6, 1), ends_on=date(2026, 5, 1)
        )


@pytest.mark.integration
def test_delete_warranty(db_session: Session) -> None:
    from datetime import date

    equip = EquipmentFactory()
    db_session.flush()
    w = services.create_warranty(
        db_session,
        equipment_id=equip.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )
    wid = w.id

    services.delete_warranty(db_session, w)

    assert db_session.get(EquipmentWarranty, wid) is None


@pytest.mark.integration
def test_require_warranty_bad_hex(db_session: Session) -> None:
    equip = EquipmentFactory()
    db_session.flush()

    with pytest.raises(ValueError, match="invalid"):
        services.require_warranty(db_session, "not-hex", equip)


@pytest.mark.integration
def test_require_warranty_not_found(db_session: Session) -> None:
    from service_crm.shared import ulid

    equip = EquipmentFactory()
    db_session.flush()

    with pytest.raises(ValueError, match="not found"):
        services.require_warranty(db_session, ulid.new().hex(), equip)


@pytest.mark.integration
def test_require_warranty_wrong_equipment(db_session: Session) -> None:
    from datetime import date

    equip_a = EquipmentFactory()
    equip_b = EquipmentFactory()
    db_session.flush()
    w = services.create_warranty(
        db_session,
        equipment_id=equip_a.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )

    with pytest.raises(ValueError):
        services.require_warranty(db_session, w.id.hex(), equip_b)


# ── Lookups ───────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_controller_types(db_session: Session) -> None:
    # The migration seeds 8 controller types; at least one must be present.
    items = services.list_controller_types(db_session)
    assert len(items) >= 1


@pytest.mark.integration
def test_list_equipment_models_empty(db_session: Session) -> None:
    items = services.list_equipment_models(db_session)
    assert isinstance(items, list)


@pytest.mark.integration
def test_list_equipment_models_returns_results(db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="Haas", model="VF-2")
    EquipmentModelFactory(manufacturer="Mazak", model="QT-250")
    db_session.flush()

    items = services.list_equipment_models(db_session)
    manufacturers = [em.manufacturer for em in items]
    assert "Haas" in manufacturers
    assert "Mazak" in manufacturers
