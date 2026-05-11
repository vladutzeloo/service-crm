"""Model-level tests for the equipment blueprint: relationships, constraints, cascades."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    ClientFactory,
    EquipmentControllerTypeFactory,
    EquipmentFactory,
    EquipmentModelFactory,
    LocationFactory,
)


@pytest.mark.integration
def test_equipment_cascade_delete_with_client(db_session: Session) -> None:
    client = ClientFactory()
    equip = EquipmentFactory(_client=client)
    db_session.flush()
    eid = equip.id

    db_session.delete(client)
    db_session.flush()

    from service_crm.equipment.models import Equipment

    assert db_session.get(Equipment, eid) is None


@pytest.mark.integration
def test_warranty_cascade_delete_with_equipment(db_session: Session) -> None:
    from datetime import date

    from service_crm.equipment.models import EquipmentWarranty

    equip = EquipmentFactory()
    db_session.flush()
    w = EquipmentWarranty(
        equipment_id=equip.id,
        starts_on=date(2026, 1, 1),
        ends_on=date(2027, 1, 1),
    )
    db_session.add(w)
    db_session.flush()
    wid = w.id

    db_session.delete(equip)
    db_session.flush()

    assert db_session.get(EquipmentWarranty, wid) is None


@pytest.mark.integration
def test_equipment_location_set_null_on_location_delete(db_session: Session) -> None:
    """Deleting a location nullifies equipment.location_id (SET NULL)."""
    client = ClientFactory()
    loc = LocationFactory(client=client)
    equip = EquipmentFactory(_client=client, _location=loc)
    db_session.flush()
    eid = equip.id

    db_session.delete(loc)
    db_session.flush()

    from service_crm.equipment.models import Equipment

    refreshed = db_session.get(Equipment, eid)
    assert refreshed is not None
    assert refreshed.location_id is None


@pytest.mark.integration
def test_equipment_model_relationship(db_session: Session) -> None:
    em = EquipmentModelFactory(manufacturer="Mazak", model="VTC-800")
    EquipmentFactory(_equipment_model=em)
    db_session.flush()
    db_session.expire(em)

    assert len(em.equipment) == 1
    assert em.equipment[0].equipment_model_id == em.id


@pytest.mark.integration
def test_equipment_controller_type_relationship(db_session: Session) -> None:
    ct = EquipmentControllerTypeFactory(code="fanuc-test", name="Fanuc Test")
    EquipmentFactory(_controller_type=ct)
    db_session.flush()
    db_session.expire(ct)

    assert len(ct.equipment) == 1
    assert ct.equipment[0].controller_type_id == ct.id


@pytest.mark.integration
def test_equipment_model_unique_constraint(db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="DMG", model="DMU 50")
    db_session.flush()

    from service_crm.equipment.models import EquipmentModel

    dup = EquipmentModel(manufacturer="DMG", model="DMU 50", family="")
    db_session.add(dup)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_controller_type_unique_code(db_session: Session) -> None:
    EquipmentControllerTypeFactory(code="unique-ctrl")
    db_session.flush()

    from service_crm.equipment.models import EquipmentControllerType

    dup = EquipmentControllerType(code="unique-ctrl", name="Dup")
    db_session.add(dup)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_warranty_date_check_constraint(db_session: Session) -> None:
    """DB rejects ends_on <= starts_on on equipment_warranty."""
    from datetime import date

    from service_crm.equipment.models import EquipmentWarranty

    equip = EquipmentFactory()
    db_session.flush()
    bad = EquipmentWarranty(
        equipment_id=equip.id,
        starts_on=date(2026, 6, 1),
        ends_on=date(2026, 5, 1),
    )
    db_session.add(bad)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_equipment_serial_unique(db_session: Session) -> None:
    from service_crm.equipment.models import Equipment

    client = ClientFactory()
    EquipmentFactory(_client=client, serial="SN-001")
    db_session.flush()

    dup = Equipment(client_id=client.id, name="Other", serial="SN-001")
    db_session.add(dup)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_client_equipment_back_populates(db_session: Session) -> None:
    client = ClientFactory()
    EquipmentFactory(_client=client)
    EquipmentFactory(_client=client)
    db_session.flush()
    db_session.expire(client)

    assert len(client.equipment) == 2
    assert all(e.client_id == client.id for e in client.equipment)


@pytest.mark.integration
def test_location_equipment_back_populates(db_session: Session) -> None:
    client = ClientFactory()
    loc = LocationFactory(client=client)
    EquipmentFactory(_client=client, _location=loc)
    db_session.flush()
    db_session.expire(loc)

    assert len(loc.equipment) == 1
    assert loc.equipment[0].location_id == loc.id


@pytest.mark.integration
def test_model_reprs(db_session: Session) -> None:
    from datetime import date

    from service_crm.equipment.models import EquipmentWarranty

    em = EquipmentModelFactory(manufacturer="Haas", model="VF-2")
    ct = EquipmentControllerTypeFactory(code="haas-ctrl", name="Haas")
    equip = EquipmentFactory(name="VF2 #1", _equipment_model=em, _controller_type=ct)
    db_session.flush()
    w = EquipmentWarranty(
        equipment_id=equip.id, starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1)
    )
    db_session.add(w)
    db_session.flush()

    assert "Haas" in repr(em)
    assert "haas-ctrl" in repr(ct)
    assert "VF2 #1" in repr(equip)
    assert "2026" in repr(w)
