"""E2E tests for the planning blueprint routes."""

from __future__ import annotations

import uuid
from datetime import date, timedelta

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.planning.models import Technician, TechnicianCapacitySlot
from tests.factories import (
    TechnicianCapacitySlotFactory,
    TechnicianFactory,
    UserFactory,
)


def _tok() -> str:
    return uuid.uuid4().hex


@pytest.mark.e2e
def test_index_redirects_unauthenticated(client: FlaskClient) -> None:
    resp = client.get("/planning/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


@pytest.mark.e2e
def test_index_redirects_to_capacity(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/planning/", follow_redirects=False)
    assert resp.status_code == 302
    assert "/planning/capacity" in resp.headers["Location"]


# ── Technicians ─────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_technicians_list(client_logged_in: FlaskClient, db_session: Session) -> None:
    TechnicianFactory(display_name="Visible-tech-XYZ")
    db_session.flush()
    resp = client_logged_in.get("/planning/technicians")
    assert resp.status_code == 200
    assert b"Visible-tech-XYZ" in resp.data


@pytest.mark.e2e
def test_technicians_list_show_all(client_logged_in: FlaskClient, db_session: Session) -> None:
    TechnicianFactory(display_name="Active-A")
    TechnicianFactory(display_name="Inactive-B", is_active=False)
    db_session.flush()
    resp = client_logged_in.get("/planning/technicians?show=all")
    assert resp.status_code == 200
    assert b"Active-A" in resp.data
    assert b"Inactive-B" in resp.data


@pytest.mark.e2e
def test_technician_new_creates(client_logged_in: FlaskClient, db_session: Session) -> None:
    user = UserFactory(email="newtech@example.com")
    db_session.flush()
    resp = client_logged_in.post(
        "/planning/technicians/new",
        data={
            "user_id": user.id.hex(),
            "display_name": "Tech From Route",
            "timezone": "UTC",
            "weekly_capacity_minutes": "1000",
            "notes": "via route",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    tech = db_session.query(Technician).filter_by(user_id=user.id).one_or_none()
    assert tech is not None
    assert tech.display_name == "Tech From Route"


@pytest.mark.e2e
def test_technician_new_validation(
    client_logged_in: FlaskClient,
) -> None:
    # Empty user_id → re-renders form.
    resp = client_logged_in.post(
        "/planning/technicians/new",
        data={
            "user_id": "",
            "display_name": "X",
            "weekly_capacity_minutes": "2400",
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_technician_new_duplicate_user_flashes(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    user = UserFactory()
    TechnicianFactory(user=user)
    db_session.flush()
    resp = client_logged_in.post(
        "/planning/technicians/new",
        data={
            "user_id": user.id.hex(),
            "display_name": "dup",
            "weekly_capacity_minutes": "2400",
            "idempotency_token": _tok(),
        },
        follow_redirects=True,
    )
    # Form re-renders with flash.
    assert resp.status_code == 200


@pytest.mark.e2e
def test_technician_detail_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech = TechnicianFactory(display_name="Detail-tech-9X")
    db_session.flush()
    resp = client_logged_in.get(f"/planning/technicians/{tech.id.hex()}")
    assert resp.status_code == 200
    assert b"Detail-tech-9X" in resp.data


@pytest.mark.e2e
def test_technician_detail_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/planning/technicians/{'00' * 16}", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_technician_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech = TechnicianFactory(display_name="Editable-tech")
    db_session.flush()
    resp = client_logged_in.get(f"/planning/technicians/{tech.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/planning/technicians/{tech.id.hex()}/edit",
        data={
            "display_name": "Edited-tech-7K",
            "timezone": "UTC",
            "weekly_capacity_minutes": "1800",
            "notes": "ed",
            "is_active": "y",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    fresh = db_session.get(Technician, tech.id)
    assert fresh.display_name == "Edited-tech-7K"


@pytest.mark.e2e
def test_technician_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get(f"/planning/technicians/{'00' * 16}/edit", follow_redirects=False)
    assert resp.status_code == 302


# ── Capacity slots ──────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_slot_upsert(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech = TechnicianFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/planning/technicians/{tech.id.hex()}/slots",
        data={
            "day": "2026-06-15",
            "capacity_minutes": "240",
            "notes": "half-day",
            "idempotency_token": _tok(),
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    slot = (
        db_session.query(TechnicianCapacitySlot)
        .filter_by(technician_id=tech.id, day=date(2026, 6, 15))
        .one()
    )
    assert slot.capacity_minutes == 240


@pytest.mark.e2e
def test_slot_upsert_unknown_tech(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/planning/technicians/{'00' * 16}/slots",
        data={"day": "2026-06-15", "capacity_minutes": "60", "idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_slot_upsert_validation(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech = TechnicianFactory()
    db_session.flush()
    # Missing required ``day`` → re-render with flash.
    resp = client_logged_in.post(
        f"/planning/technicians/{tech.id.hex()}/slots",
        data={"day": "", "capacity_minutes": "60", "idempotency_token": _tok()},
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_slot_delete(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech = TechnicianFactory()
    slot = TechnicianCapacitySlotFactory(technician=tech)
    db_session.flush()
    resp = client_logged_in.post(
        f"/planning/technicians/{tech.id.hex()}/slots/{slot.id.hex()}/delete",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    assert db_session.get(TechnicianCapacitySlot, slot.id) is None


@pytest.mark.e2e
def test_slot_delete_wrong_tech(client_logged_in: FlaskClient, db_session: Session) -> None:
    tech_a = TechnicianFactory()
    tech_b = TechnicianFactory()
    slot = TechnicianCapacitySlotFactory(technician=tech_a)
    db_session.flush()
    resp = client_logged_in.post(
        f"/planning/technicians/{tech_b.id.hex()}/slots/{slot.id.hex()}/delete",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.expire_all()
    assert db_session.get(TechnicianCapacitySlot, slot.id) is not None


@pytest.mark.e2e
def test_slot_delete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        f"/planning/technicians/{'00' * 16}/slots/{'00' * 16}/delete",
        data={"idempotency_token": _tok()},
        follow_redirects=False,
    )
    assert resp.status_code == 302


# ── Capacity view ───────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_capacity_default_range(
    client_logged_in: FlaskClient, db_session: Session, frozen_clock
) -> None:
    TechnicianFactory(display_name="Cap-tech-AB")
    db_session.flush()
    resp = client_logged_in.get("/planning/capacity")
    assert resp.status_code == 200
    assert b"Cap-tech-AB" in resp.data


@pytest.mark.e2e
def test_capacity_explicit_range(client_logged_in: FlaskClient, db_session: Session) -> None:
    TechnicianFactory(display_name="Range-tech")
    db_session.flush()
    resp = client_logged_in.get("/planning/capacity?start=2026-06-01&end=2026-06-03")
    assert resp.status_code == 200
    assert b"Range-tech" in resp.data


@pytest.mark.e2e
def test_capacity_inverted_range_falls_back(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    TechnicianFactory(display_name="Inverted-tech")
    db_session.flush()
    resp = client_logged_in.get("/planning/capacity?start=2026-06-10&end=2026-06-01")
    assert resp.status_code == 200
    # Body still rendered with the technician row.
    assert b"Inverted-tech" in resp.data


@pytest.mark.e2e
def test_capacity_bad_date_falls_back(client_logged_in: FlaskClient, db_session: Session) -> None:
    TechnicianFactory(display_name="Bad-date-tech")
    db_session.flush()
    resp = client_logged_in.get("/planning/capacity?start=garbage")
    assert resp.status_code == 200


# Avoid `timedelta` import lint
_ = timedelta
