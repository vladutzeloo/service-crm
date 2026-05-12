"""Model-level tests for the equipment domain.

Covers the two constraints called out in ROADMAP 0.4.0:

- ``Equipment.location_id``, when set, must belong to ``Equipment.client_id``
  (service-layer guard, exercised at the route boundary in
  ``test_services.py``).
- ``EquipmentWarranty.ends_on > starts_on`` (DB CHECK).

Also covers cascade behaviour and the back-populated relationships used
by the detail page.
"""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import (
    ClientFactory,
    ControllerTypeFactory,
    EquipmentFactory,
    EquipmentModelFactory,
    EquipmentWarrantyFactory,
    LocationFactory,
)


@pytest.mark.integration
def test_equipment_cascade_delete_warranties(db_session: Session) -> None:
    eq = EquipmentFactory()
    w = EquipmentWarrantyFactory(equipment=eq)
    db_session.flush()
    wid = w.id

    db_session.delete(eq)
    db_session.flush()

    from service_crm.equipment.models import EquipmentWarranty

    assert db_session.get(EquipmentWarranty, wid) is None


@pytest.mark.integration
def test_client_cascade_delete_removes_equipment(db_session: Session) -> None:
    """DB-level ``ON DELETE CASCADE`` from ``client`` to ``equipment`` works.

    No ORM relationship is declared on the :class:`Client` side, so the
    session still has the equipment row in its identity map after the
    parent is deleted. We expire it explicitly to read what's actually
    in the database — which is what production code that didn't hold a
    stale reference would see.
    """
    client = ClientFactory()
    eq = EquipmentFactory(client=client)
    db_session.flush()
    eid = eq.id

    db_session.delete(client)
    db_session.flush()
    db_session.expire_all()

    from service_crm.equipment.models import Equipment

    assert db_session.get(Equipment, eid) is None


@pytest.mark.integration
def test_location_delete_sets_equipment_location_null(db_session: Session) -> None:
    """Deleting a Location must NOT delete the Equipment row — service
    history must remain queryable."""
    client = ClientFactory()
    loc = LocationFactory(client=client)
    eq = EquipmentFactory(client=client, location=loc)
    db_session.flush()
    eid = eq.id

    db_session.delete(loc)
    db_session.flush()
    db_session.expire(eq)

    from service_crm.equipment.models import Equipment

    refreshed = db_session.get(Equipment, eid)
    assert refreshed is not None
    assert refreshed.location_id is None


@pytest.mark.integration
def test_equipment_warranty_date_check_constraint(db_session: Session) -> None:
    """DB rejects ends_on <= starts_on."""
    from service_crm.equipment.models import EquipmentWarranty

    eq = EquipmentFactory()
    db_session.flush()
    bad = EquipmentWarranty(
        equipment_id=eq.id,
        starts_on=date(2026, 6, 1),
        ends_on=date(2026, 5, 1),
    )
    db_session.add(bad)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_equipment_warranty_equal_dates_rejected(db_session: Session) -> None:
    from service_crm.equipment.models import EquipmentWarranty

    eq = EquipmentFactory()
    db_session.flush()
    bad = EquipmentWarranty(
        equipment_id=eq.id,
        starts_on=date(2026, 6, 1),
        ends_on=date(2026, 6, 1),
    )
    db_session.add(bad)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_equipment_model_unique_manuf_code(db_session: Session) -> None:
    EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-300")
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        # ``factory-boy`` flushes on _create, so the duplicate insert
        # raises here — the assertion is "the second row is refused".
        EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-300")
    db_session.rollback()


@pytest.mark.integration
def test_controller_type_unique_code(db_session: Session) -> None:
    ControllerTypeFactory(code="FANUC-31i")
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        ControllerTypeFactory(code="FANUC-31i")
    db_session.rollback()


@pytest.mark.integration
def test_equipment_warranties_back_populates(db_session: Session) -> None:
    eq = EquipmentFactory()
    EquipmentWarrantyFactory(equipment=eq, starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1))
    EquipmentWarrantyFactory(equipment=eq, starts_on=date(2024, 1, 1), ends_on=date(2025, 1, 1))
    db_session.flush()
    db_session.expire(eq)

    assert len(eq.warranties) == 2


@pytest.mark.integration
def test_equipment_label_prefers_asset_tag(db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="A-001", serial_number="SN-99")
    db_session.flush()
    assert eq.label == "A-001"


@pytest.mark.integration
def test_equipment_label_falls_back_to_serial(db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="", serial_number="SN-fallback")
    db_session.flush()
    assert eq.label == "SN-fallback"


@pytest.mark.integration
def test_equipment_label_falls_back_to_model(db_session: Session) -> None:
    mdl = EquipmentModelFactory(manufacturer="Mazak", model_code="VTC-300")
    eq = EquipmentFactory(asset_tag="", serial_number="", equipment_model=mdl)
    db_session.flush()
    assert "Mazak" in eq.label


@pytest.mark.integration
def test_equipment_label_fallback_to_literal(db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="", serial_number="", equipment_model=None)
    db_session.flush()
    assert eq.label == "equipment"


@pytest.mark.integration
def test_equipment_model_label_prefers_display_name(db_session: Session) -> None:
    mdl = EquipmentModelFactory(
        manufacturer="Mazak", model_code="VTC-300", display_name="Mazak VTC-300 (5-axis)"
    )
    db_session.flush()
    assert mdl.label == "Mazak VTC-300 (5-axis)"


@pytest.mark.integration
def test_model_reprs(db_session: Session) -> None:
    eq = EquipmentFactory(asset_tag="REPR-1")
    mdl = EquipmentModelFactory(manufacturer="ACME", model_code="Z1")
    ctrl = ControllerTypeFactory(code="REPR-CT")
    w = EquipmentWarrantyFactory(
        equipment=eq, reference="WARR-1", starts_on=date(2026, 1, 1), ends_on=date(2027, 1, 1)
    )
    db_session.flush()
    assert "REPR-1" in repr(eq)
    assert "ACME" in repr(mdl)
    assert "REPR-CT" in repr(ctrl)
    assert "WARR-1" in repr(w)
