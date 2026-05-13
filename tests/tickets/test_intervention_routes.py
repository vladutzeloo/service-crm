"""E2E tests for the intervention / parts routes."""

from __future__ import annotations

import io
import uuid
from collections.abc import Iterator
from datetime import timedelta
from pathlib import Path

import pytest
from flask import Flask
from flask.testing import FlaskClient
from PIL import Image
from sqlalchemy.orm import Session

from service_crm.shared import uploads
from service_crm.tickets.intervention_models import (
    InterventionAction,
    InterventionFinding,
    PartMaster,
    ServiceIntervention,
    ServicePartUsage,
)
from service_crm.tickets.models import TicketAttachment
from tests.factories import (
    InterventionActionFactory,
    InterventionFindingFactory,
    PartMasterFactory,
    ServiceInterventionFactory,
    ServicePartUsageFactory,
    ServiceTicketFactory,
)


@pytest.fixture
def uploads_root(tmp_path: Path, app: Flask) -> Iterator[Path]:
    app.config["UPLOADS_ROOT"] = str(tmp_path)
    uploads.reset_uploads_root()
    yield tmp_path
    app.config.pop("UPLOADS_ROOT", None)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="red").save(buf, format="PNG")
    return buf.getvalue()


def _tok() -> str:
    return uuid.uuid4().hex


# ── Auth gate ───────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_intervention_new_requires_login(client: FlaskClient, db_session: Session) -> None:
    t = ServiceTicketFactory()
    db_session.flush()
    resp = client.get(f"/tickets/{t.id.hex()}/interventions/new", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── Intervention: create / detail / edit / stop / delete ────────────────────


@pytest.mark.e2e
def test_intervention_new_get(client_logged_in: FlaskClient, db_session: Session) -> None:
    t = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{t.id.hex()}/interventions/new?lang=en")
    assert resp.status_code == 200
    assert b"Start intervention" in resp.data


@pytest.mark.e2e
def test_intervention_new_post_happy(client_logged_in: FlaskClient, db_session: Session) -> None:
    t = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{t.id.hex()}/interventions/new",
        data={
            "csrf_token": "x",
            "technician_user_id": "",
            "started_at": "",
            "summary": "first run",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    iv = db_session.query(ServiceIntervention).filter_by(ticket_id=t.id).one()
    assert iv.summary == "first run"


@pytest.mark.e2e
def test_intervention_new_post_idempotency(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    t = ServiceTicketFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "technician_user_id": "",
        "started_at": "",
        "summary": "first",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/tickets/{t.id.hex()}/interventions/new", data=payload)
    client_logged_in.post(f"/tickets/{t.id.hex()}/interventions/new", data=payload)
    count = db_session.query(ServiceIntervention).filter_by(ticket_id=t.id).count()
    assert count == 1


@pytest.mark.e2e
def test_intervention_new_unknown_ticket(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/abc/interventions/new", follow_redirects=False)
    # Service raises ValueError -> we flash + redirect to list.
    assert resp.status_code == 302
    assert "/tickets/" in resp.headers["Location"]


@pytest.mark.e2e
def test_intervention_new_service_value_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    # Pass a technician id that points at no user → service raises.
    t = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{t.id.hex()}/interventions/new",
        data={
            "csrf_token": "x",
            "technician_user_id": "00" * 16,
            "started_at": "",
            "summary": "",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_intervention_detail_happy(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    resp = client_logged_in.get(
        f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}?lang=en"
    )
    assert resp.status_code == 200
    assert b"Intervention" in resp.data


@pytest.mark.e2e
def test_intervention_detail_wrong_ticket_404s(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_intervention_detail_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/abc/interventions/abcd", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_intervention_edit_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    url = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}/edit"
    resp = client_logged_in.get(url)
    assert resp.status_code == 200
    new_when = (iv.started_at + timedelta(hours=2)).strftime("%Y-%m-%dT%H:%M")
    resp = client_logged_in.post(
        url,
        data={
            "csrf_token": "x",
            "technician_user_id": "",
            "started_at": iv.started_at.strftime("%Y-%m-%dT%H:%M"),
            "ended_at": new_when,
            "summary": "done",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(iv)
    assert iv.ended_at is not None
    assert iv.summary == "done"


@pytest.mark.e2e
def test_intervention_edit_idempotent_replay(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    url = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}/edit"
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "technician_user_id": "",
        "started_at": iv.started_at.strftime("%Y-%m-%dT%H:%M"),
        "ended_at": "",
        "summary": "first",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(url, data=payload)
    payload["summary"] = "second"
    client_logged_in.post(url, data=payload)
    db_session.refresh(iv)
    assert iv.summary == "first"  # second submission deduped


@pytest.mark.e2e
def test_intervention_edit_wrong_ticket(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/edit")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_intervention_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/abc/interventions/abcd/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_intervention_edit_validation_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    url = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}/edit"
    bad_end = (iv.started_at - timedelta(minutes=5)).strftime("%Y-%m-%dT%H:%M")
    resp = client_logged_in.post(
        url,
        data={
            "csrf_token": "x",
            "technician_user_id": "",
            "started_at": iv.started_at.strftime("%Y-%m-%dT%H:%M"),
            "ended_at": bad_end,
            "summary": "",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    # Service raises ValueError → we re-render the same page.
    assert resp.status_code == 200


@pytest.mark.e2e
def test_intervention_stop(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    url = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}/stop"
    resp = client_logged_in.post(
        url,
        data={"csrf_token": "x", "idempotency_token": _tok(), "submit": "Stop"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(iv)
    assert iv.ended_at is not None


@pytest.mark.e2e
def test_intervention_stop_wrong_ticket(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/stop",
        data={"csrf_token": "x", "idempotency_token": _tok(), "submit": "Stop"},
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_intervention_stop_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    url = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}/stop"
    tok = _tok()
    client_logged_in.post(url, data={"csrf_token": "x", "idempotency_token": tok, "submit": "Stop"})
    client_logged_in.post(url, data={"csrf_token": "x", "idempotency_token": tok, "submit": "Stop"})
    db_session.refresh(iv)
    assert iv.ended_at is not None


@pytest.mark.e2e
def test_intervention_stop_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/stop",
        data={"csrf_token": "x", "idempotency_token": _tok(), "submit": "Stop"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Actions ─────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_action_create_and_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/actions",
        data={
            "csrf_token": "x",
            "description": "replaced bearing",
            "duration_minutes": "15",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302
    action = db_session.query(InterventionAction).filter_by(intervention_id=iv.id).one()
    resp = client_logged_in.post(
        base + f"/actions/{action.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 302
    assert db_session.get(InterventionAction, action.id) is None


@pytest.mark.e2e
def test_action_create_validation_error(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/actions",
        data={
            "csrf_token": "x",
            "description": "",  # required
            "duration_minutes": "",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    # Form-level validation flashes + redirects to detail.
    assert resp.status_code == 302


@pytest.mark.e2e
def test_action_create_service_error(
    client_logged_in: FlaskClient, db_session: Session, monkeypatch
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    # Force the service into the negative-duration branch via form value
    # bypassing wtforms-level validation by feeding an extreme number.
    from service_crm.tickets import intervention_services

    def _bad(*args, **kwargs):
        raise ValueError("nope")

    monkeypatch.setattr(intervention_services, "add_action", _bad)
    resp = client_logged_in.post(
        base + "/actions",
        data={
            "csrf_token": "x",
            "description": "x",
            "duration_minutes": "0",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_action_create_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "description": "x",
        "duration_minutes": "",
        "idempotency_token": tok,
        "submit": "Add",
    }
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    client_logged_in.post(base + "/actions", data=payload)
    client_logged_in.post(base + "/actions", data=payload)
    count = db_session.query(InterventionAction).filter_by(intervention_id=iv.id).count()
    assert count == 1


@pytest.mark.e2e
def test_action_create_unknown_intervention(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/actions",
        data={"csrf_token": "x", "description": "x", "idempotency_token": _tok(), "submit": "Add"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_action_create_wrong_ticket(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/actions",
        data={"csrf_token": "x", "description": "x", "idempotency_token": _tok(), "submit": "Add"},
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_action_delete_wrong_intervention(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    a = InterventionActionFactory()
    other = ServiceInterventionFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.ticket_id.hex()}/interventions/{other.id.hex()}/actions/{a.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_action_delete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/actions/abcd/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Findings ────────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_finding_create_and_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/findings",
        data={
            "csrf_token": "x",
            "description": "encoder dropout",
            "is_root_cause": "y",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302
    f = db_session.query(InterventionFinding).filter_by(intervention_id=iv.id).one()
    assert f.is_root_cause is True

    resp = client_logged_in.post(
        base + f"/findings/{f.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 302
    assert db_session.get(InterventionFinding, f.id) is None


@pytest.mark.e2e
def test_finding_create_validation_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/findings",
        data={
            "csrf_token": "x",
            "description": "",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_finding_create_service_error(
    client_logged_in: FlaskClient, db_session: Session, monkeypatch
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    from service_crm.tickets import intervention_services

    def _bad(*args, **kwargs):
        raise ValueError("nope")

    monkeypatch.setattr(intervention_services, "add_finding", _bad)
    resp = client_logged_in.post(
        base + "/findings",
        data={"csrf_token": "x", "description": "x", "idempotency_token": _tok(), "submit": "Add"},
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_finding_create_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "description": "x",
        "idempotency_token": tok,
        "submit": "Add",
    }
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    client_logged_in.post(base + "/findings", data=payload)
    client_logged_in.post(base + "/findings", data=payload)
    count = db_session.query(InterventionFinding).filter_by(intervention_id=iv.id).count()
    assert count == 1


@pytest.mark.e2e
def test_finding_create_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/findings",
        data={"csrf_token": "x", "description": "x", "idempotency_token": _tok(), "submit": "Add"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_finding_create_wrong_ticket(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/findings",
        data={"csrf_token": "x", "description": "x", "idempotency_token": _tok(), "submit": "Add"},
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_finding_delete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/findings/abcd/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_finding_delete_wrong_intervention(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    f = InterventionFindingFactory()
    other = ServiceInterventionFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.ticket_id.hex()}/interventions/{other.id.hex()}/findings/{f.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 404


# ── Part usage ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_part_usage_create_and_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    part = PartMasterFactory(code="P-1", description="Bearing")
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/parts",
        data={
            "csrf_token": "x",
            "part_id": part.id.hex(),
            "part_code": "",
            "description": "",
            "quantity": "3",
            "unit": "pcs",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302
    usage = db_session.query(ServicePartUsage).filter_by(intervention_id=iv.id).one()
    assert usage.quantity == 3
    resp = client_logged_in.post(
        base + f"/parts/{usage.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 302
    assert db_session.get(ServicePartUsage, usage.id) is None


@pytest.mark.e2e
def test_part_usage_create_validation_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/parts",
        data={
            "csrf_token": "x",
            "quantity": "",  # required
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_part_usage_create_service_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    # Submitting with no part_id and blank code triggers the
    # service-layer "part code is required" branch.
    resp = client_logged_in.post(
        base + "/parts",
        data={
            "csrf_token": "x",
            "part_id": "",
            "part_code": "",
            "description": "",
            "quantity": "1",
            "unit": "pcs",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_part_usage_create_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    tok = _tok()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    payload = {
        "csrf_token": "x",
        "part_id": "",
        "part_code": "ADHOC",
        "description": "",
        "quantity": "1",
        "unit": "pcs",
        "idempotency_token": tok,
        "submit": "Add",
    }
    client_logged_in.post(base + "/parts", data=payload)
    client_logged_in.post(base + "/parts", data=payload)
    count = db_session.query(ServicePartUsage).filter_by(intervention_id=iv.id).count()
    assert count == 1


@pytest.mark.e2e
def test_part_usage_create_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/parts",
        data={"csrf_token": "x", "quantity": "1", "idempotency_token": _tok(), "submit": "Add"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_part_usage_create_wrong_ticket(client_logged_in: FlaskClient, db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/parts",
        data={
            "csrf_token": "x",
            "quantity": "1",
            "part_code": "X",
            "idempotency_token": _tok(),
            "submit": "Add",
        },
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_part_usage_delete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/parts/abcd/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_part_usage_delete_wrong_intervention(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    usage = ServicePartUsageFactory()
    other = ServiceInterventionFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.ticket_id.hex()}/interventions/{other.id.hex()}/parts/{usage.id.hex()}/delete",
        data={"csrf_token": "x"},
    )
    assert resp.status_code == 404


# ── Photo upload + download ─────────────────────────────────────────────────


@pytest.mark.e2e
def test_photo_upload_and_download(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(_png_bytes()), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302
    attachment = db_session.query(TicketAttachment).filter_by(intervention_id=iv.id).one()
    resp = client_logged_in.get(base + f"/photos/{attachment.id.hex()}")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_photo_upload_validation_error(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    # No file part → FileRequired fails.
    resp = client_logged_in.post(
        base + "/photos",
        data={"csrf_token": "x", "idempotency_token": _tok(), "submit": "Upload"},
        content_type="multipart/form-data",
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_photo_upload_rejected_bad_content(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    resp = client_logged_in.post(
        base + "/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(b"not an image"), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    # UploadRejected → flash + redirect (no row inserted).
    assert resp.status_code == 302
    assert db_session.query(TicketAttachment).filter_by(intervention_id=iv.id).count() == 0


@pytest.mark.e2e
def test_photo_upload_idempotent(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "upload": (io.BytesIO(_png_bytes()), "p.png"),
        "idempotency_token": tok,
        "submit": "Upload",
    }
    client_logged_in.post(base + "/photos", data=payload, content_type="multipart/form-data")
    payload2 = dict(payload)
    payload2["upload"] = (io.BytesIO(_png_bytes()), "p.png")
    client_logged_in.post(base + "/photos", data=payload2, content_type="multipart/form-data")
    count = db_session.query(TicketAttachment).filter_by(intervention_id=iv.id).count()
    assert count == 1


@pytest.mark.e2e
def test_photo_upload_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/tickets/abc/interventions/abcd/photos",
        data={"csrf_token": "x", "idempotency_token": _tok(), "submit": "Upload"},
        content_type="multipart/form-data",
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_photo_upload_wrong_ticket(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    other = ServiceTicketFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/tickets/{other.id.hex()}/interventions/{iv.id.hex()}/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(_png_bytes()), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_photo_download_unknown_attachment(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/abc/interventions/abcd/photos/abcd")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_photo_download_attachment_belongs_other_intervention(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv1 = ServiceInterventionFactory()
    iv2 = ServiceInterventionFactory(ticket=iv1.ticket)
    db_session.flush()
    # Upload against iv1, then attempt to fetch against iv2 → 404.
    base = f"/tickets/{iv1.ticket_id.hex()}/interventions/{iv1.id.hex()}"
    client_logged_in.post(
        base + "/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(_png_bytes()), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    attachment = db_session.query(TicketAttachment).filter_by(intervention_id=iv1.id).one()
    resp = client_logged_in.get(
        f"/tickets/{iv1.ticket_id.hex()}/interventions/{iv2.id.hex()}/photos/{attachment.id.hex()}"
    )
    assert resp.status_code == 404


@pytest.mark.e2e
def test_photo_download_inactive(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    client_logged_in.post(
        base + "/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(_png_bytes()), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    attachment = db_session.query(TicketAttachment).filter_by(intervention_id=iv.id).one()
    attachment.is_active = False
    db_session.flush()
    resp = client_logged_in.get(base + f"/photos/{attachment.id.hex()}")
    assert resp.status_code == 404


@pytest.mark.e2e
def test_photo_download_missing_file(
    client_logged_in: FlaskClient, db_session: Session, uploads_root: Path
) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    base = f"/tickets/{iv.ticket_id.hex()}/interventions/{iv.id.hex()}"
    client_logged_in.post(
        base + "/photos",
        data={
            "csrf_token": "x",
            "upload": (io.BytesIO(_png_bytes()), "p.png"),
            "idempotency_token": _tok(),
            "submit": "Upload",
        },
        content_type="multipart/form-data",
    )
    attachment = db_session.query(TicketAttachment).filter_by(intervention_id=iv.id).one()
    # Delete the bytes on disk; the metadata row stays.
    from service_crm.shared import uploads as _uploads

    _uploads.delete_stored(attachment.storage_key)
    resp = client_logged_in.get(base + f"/photos/{attachment.id.hex()}")
    assert resp.status_code == 404


# ── Parts admin ─────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_parts_list_and_filter(client_logged_in: FlaskClient, db_session: Session) -> None:
    PartMasterFactory(code="VISIBLE-PART-A")
    PartMasterFactory(code="VISIBLE-PART-B", is_active=False)
    db_session.flush()
    resp = client_logged_in.get("/tickets/parts")
    assert b"VISIBLE-PART-A" in resp.data
    assert b"VISIBLE-PART-B" not in resp.data
    resp = client_logged_in.get("/tickets/parts?show=all")
    assert b"VISIBLE-PART-B" in resp.data
    resp = client_logged_in.get("/tickets/parts?q=PART-A")
    assert b"VISIBLE-PART-A" in resp.data


@pytest.mark.e2e
def test_part_new_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.get("/tickets/parts/new")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        "/tickets/parts/new",
        data={
            "csrf_token": "x",
            "code": "NEW-1",
            "description": "Spindle",
            "unit": "pcs",
            "notes": "",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(PartMaster).filter_by(code="NEW-1").one().description == "Spindle"


@pytest.mark.e2e
def test_part_new_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "code": "IDEM-1",
        "description": "",
        "unit": "pcs",
        "notes": "",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/tickets/parts/new", data=payload)
    client_logged_in.post("/tickets/parts/new", data=payload)
    count = db_session.query(PartMaster).filter_by(code="IDEM-1").count()
    assert count == 1


@pytest.mark.e2e
def test_part_new_duplicate(client_logged_in: FlaskClient) -> None:
    payload = {
        "csrf_token": "x",
        "code": "DUP-1",
        "description": "",
        "unit": "pcs",
        "notes": "",
        "idempotency_token": _tok(),
        "submit": "Save",
    }
    client_logged_in.post("/tickets/parts/new", data=payload)
    payload2 = dict(payload, idempotency_token=_tok())
    resp = client_logged_in.post("/tickets/parts/new", data=payload2, follow_redirects=True)
    assert resp.status_code == 200


@pytest.mark.e2e
def test_part_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    part = PartMasterFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/tickets/parts/{part.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/tickets/parts/{part.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "description": "Updated",
            "unit": "kg",
            "notes": "n",
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(part)
    assert part.description == "Updated"
    assert part.unit == "kg"


@pytest.mark.e2e
def test_part_edit_idempotent_replay(client_logged_in: FlaskClient, db_session: Session) -> None:
    part = PartMasterFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "description": "first",
        "unit": "pcs",
        "notes": "",
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/tickets/parts/{part.id.hex()}/edit", data=payload)
    payload["description"] = "second"
    client_logged_in.post(f"/tickets/parts/{part.id.hex()}/edit", data=payload)
    db_session.refresh(part)
    assert part.description == "first"


@pytest.mark.e2e
def test_part_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/tickets/parts/aa/edit", follow_redirects=False)
    assert resp.status_code == 302
