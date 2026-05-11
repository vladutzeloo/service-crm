"""Model-level tests: relationships, constraints, cascade behaviour."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from tests.factories import ClientFactory, ContactFactory, ContractFactory, LocationFactory


@pytest.mark.integration
def test_client_contacts_cascade_delete(db_session: Session) -> None:
    client = ClientFactory()
    contact = ContactFactory(client=client)
    db_session.flush()
    contact_id = contact.id

    db_session.delete(client)
    db_session.flush()

    from service_crm.clients.models import Contact

    assert db_session.get(Contact, contact_id) is None


@pytest.mark.integration
def test_client_locations_cascade_delete(db_session: Session) -> None:
    client = ClientFactory()
    location = LocationFactory(client=client)
    db_session.flush()
    lid = location.id

    db_session.delete(client)
    db_session.flush()

    from service_crm.clients.models import Location

    assert db_session.get(Location, lid) is None


@pytest.mark.integration
def test_client_contracts_cascade_delete(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    contract = ContractFactory(
        client=client, starts_on=date(2026, 1, 1), ends_on=date(2026, 12, 31)
    )
    db_session.flush()
    cid = contract.id

    db_session.delete(client)
    db_session.flush()

    from service_crm.clients.models import ServiceContract

    assert db_session.get(ServiceContract, cid) is None


@pytest.mark.integration
def test_contact_relationship_back_populates(db_session: Session) -> None:
    client = ClientFactory()
    ContactFactory(client=client)
    ContactFactory(client=client)
    db_session.flush()
    db_session.expire(client)

    assert len(client.contacts) == 2
    assert all(c.client_id == client.id for c in client.contacts)


@pytest.mark.integration
def test_location_relationship_back_populates(db_session: Session) -> None:
    client = ClientFactory()
    LocationFactory(client=client)
    db_session.flush()
    db_session.expire(client)

    assert len(client.locations) == 1
    assert client.locations[0].client_id == client.id


@pytest.mark.integration
def test_service_contract_date_check_constraint(db_session: Session) -> None:
    """DB rejects ends_on <= starts_on."""
    from datetime import date

    from service_crm.clients.models import ServiceContract

    client = ClientFactory()
    db_session.flush()
    bad = ServiceContract(
        client_id=client.id,
        title="Bad dates",
        starts_on=date(2026, 6, 1),
        ends_on=date(2026, 5, 1),  # before starts_on
    )
    db_session.add(bad)
    with pytest.raises((IntegrityError, Exception)):
        db_session.flush()
    db_session.rollback()


@pytest.mark.integration
def test_service_contract_null_ends_on_allowed(db_session: Session) -> None:
    """ends_on=NULL is valid (open-ended contract)."""
    from datetime import date

    from service_crm.clients.models import ServiceContract

    client = ClientFactory()
    db_session.flush()
    contract = ServiceContract(
        client_id=client.id,
        title="Open-ended",
        starts_on=date(2026, 1, 1),
        ends_on=None,
    )
    db_session.add(contract)
    db_session.flush()
    assert contract.id is not None


@pytest.mark.integration
def test_soft_delete_does_not_cascade_contacts_via_is_active(db_session: Session) -> None:
    """Setting is_active=False does NOT delete child rows."""
    client = ClientFactory(is_active=True)
    ContactFactory(client=client)
    db_session.flush()

    client.is_active = False
    db_session.flush()

    assert len(client.contacts) == 1
