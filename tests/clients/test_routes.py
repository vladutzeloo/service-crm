"""E2E tests for the clients blueprint routes.

All routes require authentication; ``client_logged_in`` carries the
session cookie. DB assertions use ``db_session`` so they see the same
transaction as the request.
"""

from __future__ import annotations

import io

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.clients.models import Client, Contact, Location, ServiceContract
from tests.factories import ClientFactory, ContactFactory


@pytest.mark.e2e
def test_list_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/clients/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.mark.e2e
def test_list_renders_for_authenticated_user(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    ClientFactory(name="Visible Corp")
    db_session.flush()

    resp = client_logged_in.get("/clients/")
    assert resp.status_code == 200
    assert b"Visible Corp" in resp.data


@pytest.mark.e2e
def test_list_search_filters_results(client_logged_in: FlaskClient, db_session: Session) -> None:
    ClientFactory(name="Unique Name XYZ")
    ClientFactory(name="Other")
    db_session.flush()

    resp = client_logged_in.get("/clients/?q=Unique+Name+XYZ")
    assert b"Unique Name XYZ" in resp.data
    assert b"Other" not in resp.data


@pytest.mark.e2e
def test_new_client_get_renders_form(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/clients/new")
    assert resp.status_code == 200
    assert b"<form" in resp.data
    assert b'name="name"' in resp.data


@pytest.mark.e2e
def test_new_client_post_creates_and_redirects(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    resp = client_logged_in.post(
        "/clients/new",
        data={"name": "Fresh Client", "email": "fc@test.com", "phone": "", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Client).filter_by(name="Fresh Client").count() == 1


@pytest.mark.e2e
def test_new_client_post_empty_name_stays_on_form(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/clients/new",
        data={"name": "", "email": "", "phone": "", "notes": ""},
    )
    assert resp.status_code == 200
    assert b"<form" in resp.data


@pytest.mark.e2e
def test_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(name="Detail Corp", email="d@corp.com")
    db_session.flush()

    resp = client_logged_in.get(f"/clients/{c.id.hex()}")
    assert resp.status_code == 200
    assert b"Detail Corp" in resp.data


@pytest.mark.e2e
def test_detail_unknown_id_redirects(client_logged_in: FlaskClient) -> None:
    from service_crm.shared import ulid

    resp = client_logged_in.get(f"/clients/{ulid.new().hex()}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_edit_client_get_prefills_form(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(name="Editable Corp")
    db_session.flush()

    resp = client_logged_in.get(f"/clients/{c.id.hex()}/edit")
    assert resp.status_code == 200
    assert b"Editable Corp" in resp.data


@pytest.mark.e2e
def test_edit_client_post_updates_and_redirects(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    c = ClientFactory(name="Before Edit")
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/edit",
        data={"name": "After Edit", "email": "", "phone": "", "notes": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(c)
    assert c.name == "After Edit"


@pytest.mark.e2e
def test_deactivate_client(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(is_active=True)
    db_session.flush()

    resp = client_logged_in.post(f"/clients/{c.id.hex()}/deactivate", follow_redirects=False)
    assert resp.status_code == 302
    db_session.expire(c)
    assert c.is_active is False


@pytest.mark.e2e
def test_reactivate_client(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(is_active=False)
    db_session.flush()

    resp = client_logged_in.post(f"/clients/{c.id.hex()}/reactivate", follow_redirects=False)
    assert resp.status_code == 302
    db_session.expire(c)
    assert c.is_active is True


@pytest.mark.e2e
def test_contact_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contacts",
        data={
            "contact-name": "Jane Doe",
            "contact-role": "Purchasing",
            "contact-email": "jane@corp.com",
            "contact-phone": "",
            "contact-is_primary": "y",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Contact).filter_by(name="Jane Doe").count() == 1


@pytest.mark.e2e
def test_contact_create_missing_name_flashes_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    c = ClientFactory()
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contacts",
        data={"contact-name": "", "contact-email": ""},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"flash-error" in resp.data


@pytest.mark.e2e
def test_contact_update(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    contact = ContactFactory(client=c, name="Original")
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contacts/{contact.id.hex()}",
        data={"contact-name": "Updated", "contact-email": ""},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(contact)
    assert contact.name == "Updated"


@pytest.mark.e2e
def test_contact_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    contact = ContactFactory(client=c)
    db_session.flush()
    cid = contact.id

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contacts/{contact.id.hex()}/delete",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.get(Contact, cid) is None


@pytest.mark.e2e
def test_location_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/locations",
        data={"location-label": "Main Site", "location-city": "Cluj", "location-country": "RO"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Location).filter_by(label="Main Site").count() == 1


@pytest.mark.e2e
def test_contract_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contracts",
        data={
            "contract-title": "SLA 2026",
            "contract-reference": "REF-001",
            "contract-starts_on": "2026-01-01",
            "contract-ends_on": "2026-12-31",
            "contract-notes": "",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(ServiceContract).filter_by(title="SLA 2026").count() == 1


@pytest.mark.e2e
def test_contract_create_bad_dates_flashes_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    c = ClientFactory()
    db_session.flush()

    resp = client_logged_in.post(
        f"/clients/{c.id.hex()}/contracts",
        data={
            "contract-title": "Bad",
            "contract-starts_on": "2026-06-01",
            "contract-ends_on": "2026-05-01",
            "contract-notes": "",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"flash-error" in resp.data


@pytest.mark.e2e
def test_import_get_renders_form(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/clients/import")
    assert resp.status_code == 200
    assert b"<form" in resp.data


@pytest.mark.e2e
def test_import_post_happy_path(client_logged_in: FlaskClient, db_session: Session) -> None:
    csv_data = b"name,email\nImported Ltd,i@ltd.com\n"

    resp = client_logged_in.post(
        "/clients/import",
        data={"csv_file": (io.BytesIO(csv_data), "clients.csv")},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(Client).filter_by(name="Imported Ltd").count() == 1
