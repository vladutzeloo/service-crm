"""E2E tests for the tickets blueprint routes."""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.shared import uploads
from service_crm.tickets.models import (
    ServiceTicket,
    TicketAttachment,
    TicketComment,
    TicketPriority,
    TicketStatusHistory,
    TicketType,
)
from service_crm.tickets.state import TicketStatus
from tests.factories import (
    ClientFactory,
    EquipmentFactory,
    ServiceTicketFactory,
    TicketCommentFactory,
    UserFactory,
)


@pytest.fixture
def uploads_root(tmp_path: Path, app: Flask) -> Iterator[Path]:
    with app.app_context():
        app.config["UPLOADS_ROOT"] = str(tmp_path)
        uploads.reset_uploads_root()
        yield tmp_path
        app.config.pop("UPLOADS_ROOT", None)


def _tok() -> str:
    return uuid.uuid4().hex


# ── Auth gate ───────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_list_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/tickets/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── List ────────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ServiceTicketFactory(title="Visible-ticket-title-XYZ", number=12345)
    db_session.flush()
    resp = client_logged_in.get("/tickets/")
    assert resp.status_code == 200
    assert b"Visible-ticket-title-XYZ" in resp.data


@pytest.mark.e2e
def test_list_filters_by_status(client_logged_in: FlaskClient, db_session: Session) -> None:
    ServiceTicketFactory(title="open-one", number=100, status=TicketStatus.NEW.value)
    ServiceTicketFactory(title="closed-one", number=101, status=TicketStatus.CLOSED.value)
    db_session.flush()
    resp = client_logged_in.get("/tickets/?status=closed")
    assert b"closed-one" in resp.data
    assert b"open-one" not in resp.data


@pytest.mark.e2e
def test_list_open_show_filters_terminal(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    ServiceTicketFactory(title="MarkerOpenOne", number=200, status=TicketStatus.NEW.value)
    ServiceTicketFactory(title="MarkerClosedOne", number=201, status=TicketStatus.CLOSED.value)
    db_session.flush()
    resp = client_logged_in.get("/tickets/?show=open")
    assert b"MarkerOpenOne" in resp.data
    assert b"MarkerClosedOne" not in resp.data


@pytest.mark.e2e
def test_list_show_all(client_logged_in: FlaskClient, db_session: Session) -> None:
    ServiceTicketFactory(title="visible-all", number=210, status=TicketStatus.CLOSED.value)
    db_session.flush()
    resp = client_logged_in.get("/tickets/?show=all")
    assert b"visible-all" in resp.data


@pytest.mark.e2e
def test_list_search(client_logged_in: FlaskClient, db_session: Session) -> None:
    ServiceTicketFactory(title="UniqueSearchTitle", number=300)
    ServiceTicketFactory(title="Another", number=301)
    db_session.flush()
    resp = client_logged_in.get("/tickets/?q=UniqueSearchTitle")
    assert b"UniqueSearchTitle" in resp.data
    assert b"Another" not in resp.data


@pytest.mark.e2e
def test_list_filters_by_client(client_logged_in: FlaskClient, db_session: Session) -> None:
    a = ClientFactory(name="ClientA")
    b = ClientFactory(name="ClientB")
    ServiceTicketFactory(client=a, title="for-a", number=400)
    ServiceTicketFactory(client=b, title="for-b", number=401)
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/?client={a.id.hex()}")
    assert b"for-a" in resp.data
    assert b"for-b" not in resp.data


@pytest.mark.e2e
def test_list_my_queue(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.get("/tickets/?assigned_to=me")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_list_assigned_to_explicit_user(client_logged_in: FlaskClient, db_session: Session) -> None:
    user = UserFactory()
    ServiceTicketFactory(assignee=user, title="mine", number=500)
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/?assigned_to={user.id.hex()}")
    assert b"mine" in resp.data


@pytest.mark.e2e
def test_list_bad_query_hex_ignored(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.get("/tickets/?client=not-hex&type_id=also-bad")
    assert resp.status_code == 200


# ── New / Edit ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_new_get_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ClientFactory(name="FormClient")
    db_session.flush()
    resp = client_logged_in.get("/tickets/new")
    assert resp.status_code == 200
    assert b"FormClient" in resp.data
    # Default seeded values populate the type / priority dropdowns
    assert b"Incident" in resp.data or b"incident" in resp.data


@pytest.mark.e2e
def test_new_get_preselected_client(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(name="Preselected")
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/new?client={c.id.hex()}")
    assert resp.status_code == 200
    assert c.id.hex().encode() in resp.data


@pytest.mark.e2e
def test_new_get_preselected_equipment_resolves_client(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    c = ClientFactory(name="EQ-Client")
    eq = EquipmentFactory(client=c, asset_tag="EQ-PRE")
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/new?equipment={eq.id.hex()}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_new_get_preselected_equipment_not_found(
    client_logged_in: FlaskClient,
) -> None:
    """``?equipment=<unknown hex>`` doesn't crash; client stays blank."""
    resp = client_logged_in.get(f"/tickets/new?equipment={'00' * 16}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_new_get_when_no_defaults_seeded(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    """Exercise the route paths where neither default type nor default
    priority is configured (both ``is_default = False``)."""
    db_session.query(TicketType).update({TicketType.is_default: False})
    db_session.query(TicketPriority).update({TicketPriority.is_default: False})
    db_session.flush()
    resp = client_logged_in.get("/tickets/new")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_new_post_creates(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory(name="Buyer")
    db_session.flush()
    resp = client_logged_in.post(
        "/tickets/new",
        data={
            "client_id": c.id.hex(),
            "title": "Help me",
            "description": "Description text",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    ticket = (
        db_session.query(ServiceTicket)
        .filter(ServiceTicket.client_id == c.id, ServiceTicket.title == "Help me")
        .one()
    )
    assert ticket.status == TicketStatus.NEW.value


@pytest.mark.e2e
def test_new_post_validation_flashes(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    db_session.flush()
    resp = client_logged_in.post(
        "/tickets/new",
        data={
            "client_id": c.id.hex(),
            "title": "",  # invalid: required
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    # Form validation fails; the page is re-rendered (200).
    assert resp.status_code == 200


@pytest.mark.e2e
def test_new_post_service_error_flashes(client_logged_in: FlaskClient, db_session: Session) -> None:
    c1 = ClientFactory()
    c2 = ClientFactory()
    eq = EquipmentFactory(client=c2)
    db_session.flush()
    resp = client_logged_in.post(
        "/tickets/new",
        data={
            "client_id": c1.id.hex(),
            "title": "title",
            "equipment_id": eq.id.hex(),  # wrong client
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"equipment does not belong" in resp.data


@pytest.mark.e2e
def test_new_post_idempotent_retry(client_logged_in: FlaskClient, db_session: Session) -> None:
    c = ClientFactory()
    db_session.flush()
    token = _tok()
    payload = {
        "client_id": c.id.hex(),
        "title": "Dedupe-target",
        "idempotency_token": token,
    }
    first = client_logged_in.post("/tickets/new", data=payload, follow_redirects=False)
    assert first.status_code == 302
    second = client_logged_in.post("/tickets/new", data=payload, follow_redirects=False)
    # Dedup path → redirect to list.
    assert second.status_code == 302
    count = (
        db_session.query(ServiceTicket)
        .filter(ServiceTicket.client_id == c.id, ServiceTicket.title == "Dedupe-target")
        .count()
    )
    assert count == 1


@pytest.mark.e2e
def test_edit_get_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(title="To-edit", number=700)
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}/edit")
    assert resp.status_code == 200
    assert b"To-edit" in resp.data


@pytest.mark.e2e
def test_edit_get_unknown_ticket_redirects(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get(f"/tickets/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_edit_post_updates(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(title="Old", number=701)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/edit",
        data={
            "client_id": ticket.client_id.hex(),
            "title": "New",
            "description": "",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(ticket)
    refreshed = db_session.get(ServiceTicket, ticket.id)
    assert refreshed is not None
    assert refreshed.title == "New"


@pytest.mark.e2e
def test_edit_post_invalid_redirects_no_change(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    ticket = ServiceTicketFactory(title="Stays", number=702)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/edit",
        data={
            "client_id": ticket.client_id.hex(),
            "title": "",
            "description": "",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    # Form rejects; re-renders the page.
    assert resp.status_code == 200


@pytest.mark.e2e
def test_edit_post_service_error(client_logged_in: FlaskClient, db_session: Session) -> None:
    c1 = ClientFactory()
    c2 = ClientFactory()
    eq = EquipmentFactory(client=c2)
    ticket = ServiceTicketFactory(client=c1, title="x", number=703)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/edit",
        data={
            "client_id": ticket.client_id.hex(),
            "title": "x",
            "equipment_id": eq.id.hex(),
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert b"equipment does not belong" in resp.data


@pytest.mark.e2e
def test_edit_post_dedup(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(title="Edge", number=704)
    db_session.flush()
    token = _tok()
    payload = {
        "client_id": ticket.client_id.hex(),
        "title": "Edge2",
        "description": "",
        "idempotency_token": token,
    }
    one = client_logged_in.post(f"/tickets/{ticket.id.hex()}/edit", data=payload)
    two = client_logged_in.post(f"/tickets/{ticket.id.hex()}/edit", data=payload)
    assert one.status_code == 302
    assert two.status_code == 302


# ── Detail ──────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(title="Detail-title", number=800)
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}")
    assert resp.status_code == 200
    assert b"Detail-title" in resp.data


@pytest.mark.e2e
def test_detail_unknown_ticket_redirects(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get(f"/tickets/{'ff' * 16}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_detail_tab_comments(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=801)
    TicketCommentFactory(ticket=ticket, body="Visible-comment-body")
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}?tab=comments")
    assert b"Visible-comment-body" in resp.data


# ── Transition ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_transition_happy_path(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.NEW.value, number=900)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/transition",
        data={
            "to_state": TicketStatus.QUALIFIED.value,
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(ticket)
    refreshed = db_session.get(ServiceTicket, ticket.id)
    assert refreshed is not None
    assert refreshed.status == TicketStatus.QUALIFIED.value


@pytest.mark.e2e
def test_transition_illegal_flashes(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.NEW.value, number=901)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/transition",
        data={
            "to_state": TicketStatus.IN_PROGRESS.value,  # skipping qualified/scheduled
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert b"cannot transition" in resp.data


@pytest.mark.e2e
def test_transition_unknown_target(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=902)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/transition?lang=en",
        data={"to_state": "bogus", "idempotency_token": _tok()},
        follow_redirects=True,
    )
    assert b"Unknown target status" in resp.data


@pytest.mark.e2e
def test_transition_unknown_ticket(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.post(
        f"/tickets/{'aa' * 16}/transition",
        data={"to_state": "qualified", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_transition_form_invalid(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=903)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/transition",
        data={"to_state": "", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_transition_cancel_requires_reason(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.NEW.value, number=904)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/transition",
        data={
            "to_state": TicketStatus.CANCELLED.value,
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert b"reason is required" in resp.data


@pytest.mark.e2e
def test_transition_dedup(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.NEW.value, number=905)
    db_session.flush()
    token = _tok()
    payload = {"to_state": TicketStatus.QUALIFIED.value, "idempotency_token": token}
    one = client_logged_in.post(f"/tickets/{ticket.id.hex()}/transition", data=payload)
    # Second submit should be deduped, not mutate state again.
    two = client_logged_in.post(f"/tickets/{ticket.id.hex()}/transition", data=payload)
    assert one.status_code == 302
    assert two.status_code == 302
    # Only the initial-create row plus the one move
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .all()
    )
    assert len(rows) == 2


# ── Comments ────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_comment_create(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=1000)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/comments",
        data={"body": "Test-comment-body-xyz", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(TicketComment).filter(TicketComment.ticket_id == ticket.id).count() == 1


@pytest.mark.e2e
def test_comment_create_empty_redirects(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=1001)
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/comments",
        data={"body": "", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_comment_create_unknown_ticket(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.post(
        f"/tickets/{'cc' * 16}/comments",
        data={"body": "hi", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_comment_create_dedup(client_logged_in: FlaskClient, db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=1002)
    db_session.flush()
    token = _tok()
    payload = {"body": "dedupe-comment", "idempotency_token": token}
    client_logged_in.post(f"/tickets/{ticket.id.hex()}/comments", data=payload)
    client_logged_in.post(f"/tickets/{ticket.id.hex()}/comments", data=payload)
    assert db_session.query(TicketComment).filter(TicketComment.ticket_id == ticket.id).count() == 1


# ── Attachments ─────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_attachment_create(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1100)
    db_session.flush()
    data = {
        "upload": (io.BytesIO(b"hello world"), "hello.txt"),
        "idempotency_token": _tok(),
    }
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).count()
        == 1
    )


@pytest.mark.e2e
def test_attachment_create_rejects_bad_extension(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1101)
    db_session.flush()
    data = {
        "upload": (io.BytesIO(b"x"), "script.exe"),
        "idempotency_token": _tok(),
    }
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    # Form-allowed validator catches it before the service layer.
    assert b"CSV" in resp.data or b"Allowed" in resp.data or b"not allowed" in resp.data


@pytest.mark.e2e
def test_attachment_create_unknown_ticket(
    client_logged_in: FlaskClient,
    uploads_root: Path,
) -> None:
    data = {
        "upload": (io.BytesIO(b"x"), "hello.txt"),
        "idempotency_token": _tok(),
    }
    resp = client_logged_in.post(
        f"/tickets/{'aa' * 16}/attachments",
        data=data,
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_attachment_download(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1102)
    db_session.flush()
    # Upload first
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"download me"), "dl.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}")
    assert resp.status_code == 200
    assert resp.data == b"download me"


@pytest.mark.e2e
def test_attachment_download_unknown(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get(f"/tickets/{'aa' * 16}/attachments/{'bb' * 16}")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_attachment_delete_requires_reason(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1103)
    db_session.flush()
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    # Missing reason → form-validation failure path.
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}/delete",
        data={"reason": "", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(a)
    refreshed = db_session.get(TicketAttachment, a.id)
    assert refreshed is not None and refreshed.is_active is True


@pytest.mark.e2e
def test_attachment_delete_happy(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1104)
    db_session.flush()
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}/delete",
        data={"reason": "mistake", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(a)
    refreshed = db_session.get(TicketAttachment, a.id)
    assert refreshed is not None and refreshed.is_active is False


@pytest.mark.e2e
def test_attachment_delete_unknown(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.post(
        f"/tickets/{'aa' * 16}/attachments/{'bb' * 16}/delete",
        data={"reason": "x", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Lookup admin ────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_types_list_renders(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/types")
    assert resp.status_code == 200
    assert b"incident" in resp.data


@pytest.mark.e2e
def test_priorities_list_renders(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/priorities")
    assert resp.status_code == 200
    assert b"normal" in resp.data


@pytest.mark.e2e
def test_type_edit_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    t = db_session.query(TicketType).filter(TicketType.code == "incident").one()
    resp = client_logged_in.get(f"/tickets/types/{t.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/tickets/types/{t.id.hex()}/edit",
        data={"label": "renamed", "is_active": "1", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(t)
    refreshed = db_session.get(TicketType, t.id)
    assert refreshed is not None and refreshed.label == "renamed"


@pytest.mark.e2e
def test_type_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/tickets/types/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_priority_edit_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    p = db_session.query(TicketPriority).filter(TicketPriority.code == "normal").one()
    resp = client_logged_in.get(f"/tickets/priorities/{p.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/tickets/priorities/{p.id.hex()}/edit",
        data={"label": "renamed-p", "is_active": "1", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire(p)
    refreshed = db_session.get(TicketPriority, p.id)
    assert refreshed is not None and refreshed.label == "renamed-p"


@pytest.mark.e2e
def test_priority_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/tickets/priorities/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_new_post_no_token_falls_through(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    """A submit without an idempotency token still proceeds — there's
    nothing to dedupe against, and forms that pre-date 0.2.0's wiring
    must keep working."""
    c = ClientFactory()
    db_session.flush()
    resp = client_logged_in.post(
        "/tickets/new",
        data={
            "client_id": c.id.hex(),
            "title": "no-token-ticket",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert (
        db_session.query(ServiceTicket).filter(ServiceTicket.title == "no-token-ticket").count()
        == 1
    )


# ── Edge-case branches that don't fit in the happy-path groups above ─────────


@pytest.mark.e2e
def test_comment_create_service_error_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    """Force ``services.add_comment`` to raise so the ValueError branch
    of the route is exercised.

    The body must be short enough to pass the form's ``Length(max=8000)``
    char-count check but heavy enough that the UTF-8 byte cap in the
    service layer rejects it. Emojis are 4 bytes each in UTF-8.
    """
    ticket = ServiceTicketFactory(number=1200)
    db_session.flush()
    too_big_bytes = "🛠" * 3000  # 3000 chars, 12000 bytes — exceeds 8 KB cap
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/comments",
        data={"body": too_big_bytes, "idempotency_token": _tok()},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert b"exceeds" in resp.data


@pytest.mark.e2e
def test_attachment_create_dedup(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1300)
    db_session.flush()
    token = _tok()
    # First upload succeeds.
    first = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": token},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert first.status_code == 302
    # Second submit with same token deduplicates.
    second = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": token},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert second.status_code == 302
    assert (
        db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).count()
        == 1
    )


@pytest.mark.e2e
def test_attachment_create_upload_rejected_flashes(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    """Magic-byte mismatch is caught by the service layer's
    ``UploadRejected`` branch, not by WTForms ``FileAllowed``."""
    ticket = ServiceTicketFactory(number=1301)
    db_session.flush()
    fake_pdf = io.BytesIO(b"not actually a pdf payload" + b"\x00" * 60)
    resp = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (fake_pdf, "doc.pdf"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
        follow_redirects=True,
    )
    assert b"does not match" in resp.data


@pytest.mark.e2e
def test_attachment_download_inactive_404(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    """A soft-deleted attachment 404s rather than streaming."""
    ticket = ServiceTicketFactory(number=1400)
    db_session.flush()
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    a.is_active = False
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_attachment_download_missing_file_404(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    """If the bytes vanish from disk we 404 rather than 500."""
    ticket = ServiceTicketFactory(number=1401)
    db_session.flush()
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    (uploads_root / a.storage_key).unlink()
    resp = client_logged_in.get(f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_attachment_delete_dedup(
    client_logged_in: FlaskClient,
    db_session: Session,
    uploads_root: Path,
) -> None:
    ticket = ServiceTicketFactory(number=1500)
    db_session.flush()
    client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments",
        data={"upload": (io.BytesIO(b"x"), "x.txt"), "idempotency_token": _tok()},
        content_type="multipart/form-data",
    )
    db_session.expire_all()
    a = db_session.query(TicketAttachment).filter(TicketAttachment.ticket_id == ticket.id).one()
    token = _tok()
    payload = {"reason": "mistake", "idempotency_token": token}
    one = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}/delete", data=payload
    )
    two = client_logged_in.post(
        f"/tickets/{ticket.id.hex()}/attachments/{a.id.hex()}/delete", data=payload
    )
    assert one.status_code == 302
    assert two.status_code == 302
