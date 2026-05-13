"""Service-layer tests for the v0.6 intervention / parts surface."""

from __future__ import annotations

import io
from datetime import UTC, datetime, timedelta

import pytest
from PIL import Image
from sqlalchemy.orm import Session

from service_crm.shared.uploads import UploadRejected
from service_crm.tickets import intervention_services
from service_crm.tickets.intervention_models import (
    InterventionAction,
    InterventionFinding,
    ServicePartUsage,
)
from tests.factories import (
    InterventionActionFactory,
    InterventionFindingFactory,
    PartMasterFactory,
    ServiceInterventionFactory,
    ServicePartUsageFactory,
    ServiceTicketFactory,
    UserFactory,
)


def _png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (32, 32), color="white").save(buf, format="PNG")
    return buf.getvalue()


# ── Interventions ────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_require_intervention_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid intervention id"):
        intervention_services.require_intervention(db_session, "not-hex")


@pytest.mark.integration
def test_require_intervention_missing(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        intervention_services.require_intervention(db_session, "00" * 16)


@pytest.mark.integration
def test_create_intervention_defaults(db_session: Session, frozen_clock: datetime) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    iv = intervention_services.create_intervention(
        db_session,
        ticket_id=ticket.id,
        technician_user_id=None,
    )
    assert iv.started_at == frozen_clock
    assert iv.is_open


@pytest.mark.integration
def test_create_intervention_with_technician(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    tech = UserFactory()
    db_session.flush()
    iv = intervention_services.create_intervention(
        db_session,
        ticket_id=ticket.id,
        technician_user_id=tech.id,
        summary="setup",
    )
    assert iv.technician_user_id == tech.id


@pytest.mark.integration
def test_create_intervention_requires_ticket(db_session: Session) -> None:
    with pytest.raises(ValueError, match="ticket not found"):
        intervention_services.create_intervention(
            db_session, ticket_id=b"\x00" * 16, technician_user_id=None
        )


@pytest.mark.integration
def test_create_intervention_unknown_technician(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="technician not found"):
        intervention_services.create_intervention(
            db_session,
            ticket_id=ticket.id,
            technician_user_id=b"\x01" * 16,
        )


@pytest.mark.integration
def test_create_intervention_inactive_technician(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    tech = UserFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        intervention_services.create_intervention(
            db_session,
            ticket_id=ticket.id,
            technician_user_id=tech.id,
        )


@pytest.mark.integration
def test_update_intervention_happy(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    tech = UserFactory()
    db_session.flush()
    new_start = iv.started_at
    new_end = new_start + timedelta(hours=1)
    intervention_services.update_intervention(
        db_session,
        iv,
        technician_user_id=tech.id,
        started_at=new_start,
        ended_at=new_end,
        summary=" did stuff ",
    )
    assert iv.technician_user_id == tech.id
    assert iv.ended_at == new_end
    assert iv.summary == "did stuff"


@pytest.mark.integration
def test_update_intervention_inconsistent_times(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ended_at"):
        intervention_services.update_intervention(
            db_session,
            iv,
            technician_user_id=None,
            started_at=iv.started_at,
            ended_at=iv.started_at - timedelta(minutes=5),
            summary="",
        )


@pytest.mark.integration
def test_update_intervention_unknown_technician(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="technician not found"):
        intervention_services.update_intervention(
            db_session,
            iv,
            technician_user_id=b"\x02" * 16,
            started_at=iv.started_at,
            ended_at=None,
            summary="",
        )


@pytest.mark.integration
def test_update_intervention_inactive_technician(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    tech = UserFactory(is_active=False)
    db_session.flush()
    with pytest.raises(ValueError, match="inactive"):
        intervention_services.update_intervention(
            db_session,
            iv,
            technician_user_id=tech.id,
            started_at=iv.started_at,
            ended_at=None,
            summary="",
        )


@pytest.mark.integration
def test_stop_intervention_uses_clock(db_session: Session, frozen_clock: datetime) -> None:
    iv = ServiceInterventionFactory(started_at=datetime(2025, 1, 1, 11, 0, 0, tzinfo=UTC))
    db_session.flush()
    intervention_services.stop_intervention(db_session, iv)
    assert iv.ended_at == frozen_clock


@pytest.mark.integration
def test_stop_intervention_rejects_past(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="ended_at"):
        intervention_services.stop_intervention(
            db_session, iv, ended_at=iv.started_at - timedelta(minutes=1)
        )


@pytest.mark.integration
def test_delete_intervention(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    iid = iv.id
    intervention_services.delete_intervention(db_session, iv)
    assert db_session.get(intervention_services.ServiceIntervention, iid) is None


# ── Actions ──────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_add_action_happy(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    action = intervention_services.add_action(
        db_session,
        intervention_id=iv.id,
        description="replaced bearing",
        duration_minutes=15,
    )
    assert action.duration_minutes == 15


@pytest.mark.integration
def test_add_action_blank_description(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="description"):
        intervention_services.add_action(db_session, intervention_id=iv.id, description="   ")


@pytest.mark.integration
def test_add_action_oversize(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="exceeds"):
        intervention_services.add_action(
            db_session,
            intervention_id=iv.id,
            description="x" * (InterventionAction.DESCRIPTION_MAX_BYTES + 1),
        )


@pytest.mark.integration
def test_add_action_negative_duration(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="non-negative"):
        intervention_services.add_action(
            db_session,
            intervention_id=iv.id,
            description="x",
            duration_minutes=-1,
        )


@pytest.mark.integration
def test_add_action_unknown_intervention(db_session: Session) -> None:
    with pytest.raises(ValueError, match="intervention not found"):
        intervention_services.add_action(db_session, intervention_id=b"\x09" * 16, description="x")


@pytest.mark.integration
def test_require_and_delete_action(db_session: Session) -> None:
    a = InterventionActionFactory()
    db_session.flush()
    got = intervention_services.require_action(db_session, a.id.hex())
    assert got is a
    with pytest.raises(ValueError, match="invalid action id"):
        intervention_services.require_action(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        intervention_services.require_action(db_session, "00" * 16)
    intervention_services.delete_action(db_session, a)
    assert db_session.get(InterventionAction, a.id) is None


# ── Findings ─────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_add_finding_happy(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    f = intervention_services.add_finding(
        db_session,
        intervention_id=iv.id,
        description="axis encoder dropout",
        is_root_cause=True,
    )
    assert f.is_root_cause is True


@pytest.mark.integration
def test_add_finding_validations(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="description"):
        intervention_services.add_finding(db_session, intervention_id=iv.id, description="")
    with pytest.raises(ValueError, match="exceeds"):
        intervention_services.add_finding(
            db_session,
            intervention_id=iv.id,
            description="x" * (InterventionFinding.DESCRIPTION_MAX_BYTES + 1),
        )
    with pytest.raises(ValueError, match="intervention not found"):
        intervention_services.add_finding(db_session, intervention_id=b"\x08" * 16, description="x")


@pytest.mark.integration
def test_require_and_delete_finding(db_session: Session) -> None:
    f = InterventionFindingFactory()
    db_session.flush()
    got = intervention_services.require_finding(db_session, f.id.hex())
    assert got is f
    with pytest.raises(ValueError, match="invalid finding id"):
        intervention_services.require_finding(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        intervention_services.require_finding(db_session, "00" * 16)
    intervention_services.delete_finding(db_session, f)
    assert db_session.get(InterventionFinding, f.id) is None


# ── Parts master ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_parts_search_sqlite(db_session: Session) -> None:
    PartMasterFactory(code="SEARCH-ABC", description="Spindle bearing")
    PartMasterFactory(code="SEARCH-XYZ", description="Hose clamp")
    db_session.flush()

    def _codes(items: list) -> set[str]:
        return {p.code for p in items if p.code.startswith("SEARCH-")}

    items = intervention_services.list_parts(db_session, q="spindle bearing")
    assert _codes(items) == {"SEARCH-ABC"}
    assert _codes(intervention_services.list_parts(db_session, q="")) == {
        "SEARCH-ABC",
        "SEARCH-XYZ",
    }


@pytest.mark.integration
def test_list_parts_active_only(db_session: Session) -> None:
    PartMasterFactory(code="ACTIVE-A", is_active=True)
    PartMasterFactory(code="ACTIVE-B", is_active=False)
    db_session.flush()

    def _codes(items: list) -> set[str]:
        return {p.code for p in items if p.code.startswith("ACTIVE-")}

    assert _codes(intervention_services.list_parts(db_session)) == {"ACTIVE-A"}
    assert _codes(intervention_services.list_parts(db_session, active_only=False)) == {
        "ACTIVE-A",
        "ACTIVE-B",
    }


@pytest.mark.integration
def test_create_part_happy(db_session: Session) -> None:
    part = intervention_services.create_part(
        db_session,
        code="X-1",
        description="thing",
        unit="m",
        notes="be careful",
    )
    assert part.code == "X-1"
    assert part.unit == "m"


@pytest.mark.integration
def test_create_part_blank_code(db_session: Session) -> None:
    with pytest.raises(ValueError, match="part code"):
        intervention_services.create_part(db_session, code="")


@pytest.mark.integration
def test_create_part_duplicate_case_insensitive(db_session: Session) -> None:
    intervention_services.create_part(db_session, code="abc")
    with pytest.raises(ValueError, match="already exists"):
        intervention_services.create_part(db_session, code="ABC")


@pytest.mark.integration
def test_create_part_default_unit(db_session: Session) -> None:
    part = intervention_services.create_part(db_session, code="Y", unit=" ")
    assert part.unit == "pcs"


@pytest.mark.integration
def test_update_part(db_session: Session) -> None:
    p = PartMasterFactory()
    db_session.flush()
    intervention_services.update_part(
        db_session,
        p,
        description="new",
        unit="",
        notes="n",
        is_active=False,
    )
    assert p.description == "new"
    assert p.unit == "pcs"
    assert p.is_active is False


@pytest.mark.integration
def test_require_part(db_session: Session) -> None:
    p = PartMasterFactory()
    db_session.flush()
    assert intervention_services.require_part(db_session, p.id.hex()) is p
    with pytest.raises(ValueError, match="invalid part id"):
        intervention_services.require_part(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        intervention_services.require_part(db_session, "00" * 16)


# ── Part usage ───────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_add_part_usage_from_catalog(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    part = PartMasterFactory(description="Spindle", unit="set")
    db_session.flush()
    usage = intervention_services.add_part_usage(
        db_session,
        intervention_id=iv.id,
        part_id=part.id,
        quantity=2,
    )
    assert usage.part_code == part.code
    assert usage.description == "Spindle"
    assert usage.unit == "set"
    assert usage.quantity == 2


@pytest.mark.integration
def test_add_part_usage_caller_overrides_unit(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    part = PartMasterFactory(unit="set")
    db_session.flush()
    usage = intervention_services.add_part_usage(
        db_session,
        intervention_id=iv.id,
        part_id=part.id,
        unit="kg",
    )
    assert usage.unit == "kg"


@pytest.mark.integration
def test_add_part_usage_adhoc(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    usage = intervention_services.add_part_usage(
        db_session,
        intervention_id=iv.id,
        part_id=None,
        part_code="ADHOC-1",
        description="random",
        quantity=4,
    )
    assert usage.part_id is None
    assert usage.part_code == "ADHOC-1"
    assert usage.quantity == 4


@pytest.mark.integration
def test_add_part_usage_validations(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="quantity"):
        intervention_services.add_part_usage(
            db_session,
            intervention_id=iv.id,
            part_id=None,
            part_code="X",
            quantity=0,
        )
    with pytest.raises(ValueError, match="intervention not found"):
        intervention_services.add_part_usage(
            db_session,
            intervention_id=b"\x05" * 16,
            part_id=None,
            part_code="X",
        )
    with pytest.raises(ValueError, match="part not found"):
        intervention_services.add_part_usage(
            db_session,
            intervention_id=iv.id,
            part_id=b"\x06" * 16,
        )
    with pytest.raises(ValueError, match="part code"):
        intervention_services.add_part_usage(
            db_session,
            intervention_id=iv.id,
            part_id=None,
            part_code="",
        )


@pytest.mark.integration
def test_require_and_delete_usage(db_session: Session) -> None:
    u = ServicePartUsageFactory()
    db_session.flush()
    got = intervention_services.require_part_usage(db_session, u.id.hex())
    assert got is u
    with pytest.raises(ValueError, match="invalid part usage id"):
        intervention_services.require_part_usage(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        intervention_services.require_part_usage(db_session, "00" * 16)
    intervention_services.delete_part_usage(db_session, u)
    assert db_session.get(ServicePartUsage, u.id) is None


@pytest.mark.integration
def test_coalesce_parts_sums_duplicates(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    ServicePartUsageFactory(intervention=iv, part_code="A", description="x", quantity=2)
    ServicePartUsageFactory(intervention=iv, part_code="A", description="x", quantity=3)
    ServicePartUsageFactory(intervention=iv, part_code="B", description="y", quantity=1)
    db_session.flush()
    grouped = intervention_services.coalesce_parts(iv.parts)
    by_code = {code: (descr, qty, unit) for code, descr, qty, unit in grouped}
    assert by_code["A"] == ("x", 5, "pcs")
    assert by_code["B"] == ("y", 1, "pcs")


# ── Photo upload ─────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_add_intervention_photo_uses_uploads(db_session: Session, tmp_path) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    stream = io.BytesIO(_png_bytes())
    attachment = intervention_services.add_intervention_photo(
        db_session,
        intervention=iv,
        uploader_user_id=None,
        stream=stream,
        filename="photo.png",
        declared_content_type="image/png",
    )
    assert attachment.intervention_id == iv.id
    assert attachment.content_type == "image/webp"


@pytest.mark.integration
def test_add_intervention_photo_rejects_bad_type(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    with pytest.raises(UploadRejected):
        intervention_services.add_intervention_photo(
            db_session,
            intervention=iv,
            uploader_user_id=None,
            stream=io.BytesIO(b"not an image"),
            filename="photo.png",
            declared_content_type="image/png",
        )


@pytest.mark.integration
def test_list_intervention_photos_excludes_inactive(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    stream = io.BytesIO(_png_bytes())
    intervention_services.add_intervention_photo(
        db_session,
        intervention=iv,
        uploader_user_id=None,
        stream=stream,
        filename="p.png",
    )
    photos = intervention_services.list_intervention_photos(db_session, iv.id)
    assert len(photos) == 1
    photos[0].is_active = False
    db_session.flush()
    assert intervention_services.list_intervention_photos(db_session, iv.id) == []


@pytest.mark.integration
def test_part_search_filter_postgres_branch(db_session: Session, monkeypatch) -> None:
    """Postgres path returns a tsvector @@ tsquery expression — compile
    the SQL without executing so we exercise the lines without needing
    a real Postgres backend."""
    monkeypatch.setattr(
        "service_crm.tickets.intervention_services._dialect",
        lambda: "postgresql",
    )
    flt = intervention_services._part_search_filter("spindle")
    assert flt is not None
    assert "to_tsvector" in str(flt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.integration
def test_add_part_usage_caller_overrides_everything(db_session: Session) -> None:
    """All snapshot-fallback branches skipped: caller passes code,
    description and unit explicitly so the part-master values are
    ignored."""
    iv = ServiceInterventionFactory()
    part = PartMasterFactory(code="MASTER", description="from master", unit="set")
    db_session.flush()
    usage = intervention_services.add_part_usage(
        db_session,
        intervention_id=iv.id,
        part_id=part.id,
        part_code="OVERRIDE",
        description="override desc",
        quantity=1,
        unit="kg",
    )
    assert usage.part_code == "OVERRIDE"
    assert usage.description == "override desc"
    assert usage.unit == "kg"


@pytest.mark.integration
def test_add_part_usage_unknown_part_inputs(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    # part_id None + part_code set + caller passes "set" unit → unit stays.
    usage = intervention_services.add_part_usage(
        db_session,
        intervention_id=iv.id,
        part_id=None,
        part_code="ADHOC",
        description="d",
        quantity=2,
        unit="set",
    )
    assert usage.unit == "set"


@pytest.mark.integration
def test_aware_helper_passes_aware_through() -> None:
    from datetime import UTC, datetime

    aware = datetime(2026, 1, 1, tzinfo=UTC)
    assert intervention_services._aware(aware) is aware


@pytest.mark.integration
def test_list_for_ticket_ordering(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    first = ServiceInterventionFactory(
        ticket=ticket,
        started_at=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
    )
    second = ServiceInterventionFactory(
        ticket=ticket,
        started_at=datetime(2026, 1, 2, 10, 0, tzinfo=UTC),
    )
    db_session.flush()
    rows = intervention_services.list_for_ticket(db_session, ticket.id)
    assert [iv.id for iv in rows] == [second.id, first.id]
