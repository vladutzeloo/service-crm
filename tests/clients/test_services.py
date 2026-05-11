"""Service-layer integration tests for the clients blueprint."""

from __future__ import annotations

import pytest
from sqlalchemy.orm import Session

from service_crm.clients import services
from service_crm.clients.models import Client, Contact, Location, ServiceContract
from tests.factories import ClientFactory, ContactFactory


@pytest.mark.integration
def test_create_client(db_session: Session) -> None:
    client = services.create_client(
        db_session,
        name="  ACME Corp  ",
        email="info@acme.com",
        phone="+40 21 000 0000",
        notes="Top client",
    )
    assert client.id is not None
    assert client.name == "ACME Corp"
    assert client.email == "info@acme.com"
    assert client.is_active is True


@pytest.mark.integration
def test_update_client(db_session: Session) -> None:
    client = ClientFactory(name="Old Name")
    db_session.flush()

    services.update_client(db_session, client, name="New Name", email="new@example.com")

    assert client.name == "New Name"
    assert client.email == "new@example.com"


@pytest.mark.integration
def test_deactivate_and_reactivate_client(db_session: Session) -> None:
    client = ClientFactory(is_active=True)
    db_session.flush()

    services.deactivate_client(db_session, client)
    assert client.is_active is False

    services.reactivate_client(db_session, client)
    assert client.is_active is True


@pytest.mark.integration
def test_list_clients_active_only_by_default(db_session: Session) -> None:
    ClientFactory(name="Active", is_active=True)
    ClientFactory(name="Inactive", is_active=False)
    db_session.flush()

    items, total = services.list_clients(db_session)

    names = [c.name for c in items]
    assert "Active" in names
    assert "Inactive" not in names
    assert total >= 1


@pytest.mark.integration
def test_list_clients_all_includes_inactive(db_session: Session) -> None:
    ClientFactory(name="Active2", is_active=True)
    ClientFactory(name="Inactive2", is_active=False)
    db_session.flush()

    items, _total = services.list_clients(db_session, active_only=False)

    names = [c.name for c in items]
    assert "Active2" in names
    assert "Inactive2" in names


@pytest.mark.integration
def test_list_clients_search_by_name(db_session: Session) -> None:
    ClientFactory(name="Zanzibar Tech")
    ClientFactory(name="Other Corp")
    db_session.flush()

    items, _total = services.list_clients(db_session, q="Zanzibar")

    assert len(items) == 1
    assert items[0].name == "Zanzibar Tech"


@pytest.mark.integration
def test_list_clients_search_by_contact_name(db_session: Session) -> None:
    client = ClientFactory(name="Corp Without Name Match")
    ContactFactory(client=client, name="SearchablePerson", email="sp@corp.com")
    ClientFactory(name="Unrelated Corp")
    db_session.flush()

    items, _ = services.list_clients(db_session, q="SearchablePerson")

    names = [c.name for c in items]
    assert "Corp Without Name Match" in names
    assert "Unrelated Corp" not in names


@pytest.mark.integration
def test_get_client_returns_none_for_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    result = services.get_client(db_session, ulid.new())
    assert result is None


@pytest.mark.integration
def test_get_client_returns_existing(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()

    result = services.get_client(db_session, client.id)
    assert result is client


@pytest.mark.integration
def test_client_search_filter_postgres_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("service_crm.clients.services._dialect", lambda: "postgresql")
    flt = services._client_search_filter(db_session, "acme")
    assert flt is not None


@pytest.mark.integration
def test_client_search_filter_sqlite_path(
    db_session: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr("service_crm.clients.services._dialect", lambda: "sqlite")
    flt = services._client_search_filter(db_session, "acme")
    assert flt is not None


@pytest.mark.integration
def test_require_client_raises_on_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_client(db_session, "not-hex")


@pytest.mark.integration
def test_require_client_raises_on_missing(db_session: Session) -> None:
    from service_crm.shared import ulid

    with pytest.raises(ValueError, match="not found"):
        services.require_client(db_session, ulid.new().hex())


# ── Contacts ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_create_contact(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()

    contact = services.create_contact(
        db_session,
        client_id=client.id,
        name="Alice",
        email="alice@example.com",
        is_primary=True,
    )

    assert contact.id is not None
    assert contact.client_id == client.id
    assert contact.is_primary is True


@pytest.mark.integration
def test_update_contact(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    contact = services.create_contact(db_session, client_id=client.id, name="Old")

    services.update_contact(db_session, contact, name="New", phone="0700 000 000")

    assert contact.name == "New"
    assert contact.phone == "0700 000 000"


@pytest.mark.integration
def test_delete_contact(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    contact = services.create_contact(db_session, client_id=client.id, name="Temp")
    cid = contact.id

    services.delete_contact(db_session, contact)

    assert db_session.get(Contact, cid) is None


@pytest.mark.integration
def test_require_contact_invalid_hex(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="invalid"):
        services.require_contact(db_session, "not-hex", client)


@pytest.mark.integration
def test_require_contact_wrong_client(db_session: Session) -> None:
    client_a = ClientFactory()
    client_b = ClientFactory()
    db_session.flush()
    contact = services.create_contact(db_session, client_id=client_a.id, name="A")

    with pytest.raises(ValueError):
        services.require_contact(db_session, contact.id.hex(), client_b)


# ── Locations ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_require_location_invalid_hex(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="invalid"):
        services.require_location(db_session, "not-hex", client)


@pytest.mark.integration
def test_require_location_not_found(db_session: Session) -> None:
    from service_crm.shared import ulid

    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="not found"):
        services.require_location(db_session, ulid.new().hex(), client)


@pytest.mark.integration
def test_update_location(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    loc = services.create_location(db_session, client_id=client.id, label="Old")

    services.update_location(
        db_session, loc, label="New HQ", address="Str. X", city="Iași", country="RO"
    )

    assert loc.label == "New HQ"
    assert loc.city == "Iași"


@pytest.mark.integration
def test_create_location(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()

    loc = services.create_location(
        db_session,
        client_id=client.id,
        label="HQ",
        city="București",
        country="RO",
    )

    assert loc.id is not None
    assert loc.city == "București"


@pytest.mark.integration
def test_delete_location(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    loc = services.create_location(db_session, client_id=client.id, label="Tmp")
    lid = loc.id

    services.delete_location(db_session, loc)

    assert db_session.get(Location, lid) is None


# ── Contracts ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_require_contract_invalid_hex(db_session: Session) -> None:
    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="invalid"):
        services.require_contract(db_session, "not-hex", client)


@pytest.mark.integration
def test_require_contract_not_found(db_session: Session) -> None:
    from service_crm.shared import ulid

    client = ClientFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="not found"):
        services.require_contract(db_session, ulid.new().hex(), client)


@pytest.mark.integration
def test_update_contract_happy_path(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    db_session.flush()
    contract = services.create_contract(
        db_session,
        client_id=client.id,
        title="Original",
        starts_on=date(2026, 1, 1),
    )

    services.update_contract(
        db_session,
        contract,
        title="Updated SLA",
        reference="REF-002",
        starts_on=date(2026, 2, 1),
        ends_on=date(2026, 12, 31),
        notes="renewed",
    )

    assert contract.title == "Updated SLA"
    assert contract.reference == "REF-002"
    assert contract.ends_on == date(2026, 12, 31)


@pytest.mark.integration
def test_create_contract(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    db_session.flush()

    contract = services.create_contract(
        db_session,
        client_id=client.id,
        title="Annual SLA",
        starts_on=date(2026, 1, 1),
        ends_on=date(2026, 12, 31),
    )

    assert contract.id is not None
    assert contract.is_active is True


@pytest.mark.integration
def test_create_contract_rejects_bad_dates(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    db_session.flush()

    with pytest.raises(ValueError, match="ends_on"):
        services.create_contract(
            db_session,
            client_id=client.id,
            title="Bad",
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 5, 1),
        )


@pytest.mark.integration
def test_update_contract_rejects_bad_dates(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    db_session.flush()
    contract = services.create_contract(
        db_session,
        client_id=client.id,
        title="OK",
        starts_on=date(2026, 1, 1),
    )

    with pytest.raises(ValueError, match="ends_on"):
        services.update_contract(
            db_session,
            contract,
            title="OK",
            starts_on=date(2026, 6, 1),
            ends_on=date(2026, 5, 1),
        )


@pytest.mark.integration
def test_delete_contract(db_session: Session) -> None:
    from datetime import date

    client = ClientFactory()
    db_session.flush()
    contract = services.create_contract(
        db_session, client_id=client.id, title="Temp", starts_on=date(2026, 1, 1)
    )
    cid = contract.id

    services.delete_contract(db_session, contract)

    assert db_session.get(ServiceContract, cid) is None


# ── CSV import ────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_csv_import_happy_path(db_session: Session) -> None:
    csv_text = "name,email,phone\nTest Corp,tc@test.com,+40 21 111\nOther Inc,,\n"

    imported, errors = services.import_clients_csv(db_session, csv_text)

    assert imported == 2
    assert errors == []
    assert db_session.query(Client).filter_by(name="Test Corp").count() == 1


@pytest.mark.integration
def test_csv_import_missing_name_column(db_session: Session) -> None:
    csv_text = "email,phone\nfoo@bar.com,123\n"

    imported, errors = services.import_clients_csv(db_session, csv_text)

    assert imported == 0
    assert any("name" in e for e in errors)


@pytest.mark.integration
def test_csv_import_skips_empty_name_rows(db_session: Session) -> None:
    csv_text = "name,email\nGood Corp,g@g.com\n,no-name@x.com\n"

    imported, errors = services.import_clients_csv(db_session, csv_text)

    assert imported == 1
    assert len(errors) == 1
    assert "Row 3" in errors[0]


@pytest.mark.integration
def test_csv_import_empty_file(db_session: Session) -> None:
    imported, errors = services.import_clients_csv(db_session, "")

    assert imported == 0
    assert any("empty" in e.lower() or "header" in e.lower() for e in errors)
