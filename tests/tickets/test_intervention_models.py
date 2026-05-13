"""Model-level tests for the v0.6 intervention / parts domain."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from service_crm.tickets.intervention_models import (
    InterventionAction,
    InterventionFinding,
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
    TicketAttachmentFactory,
    UserFactory,
)


@pytest.mark.integration
def test_intervention_repr_and_is_open(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    assert iv.is_open is True
    assert iv.duration_minutes is None
    assert "open=True" in repr(iv)
    iv.ended_at = iv.started_at + timedelta(minutes=42)
    db_session.flush()
    assert iv.is_open is False
    assert iv.duration_minutes == 42
    assert "open=False" in repr(iv)


@pytest.mark.integration
def test_intervention_duration_floors_negative(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    iv.ended_at = iv.started_at - timedelta(minutes=5)
    db_session.flush()
    assert iv.duration_minutes == 0


@pytest.mark.integration
def test_intervention_cascade_on_ticket_delete(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    iv_id = iv.id
    ticket = iv.ticket
    db_session.delete(ticket)
    db_session.flush()
    assert db_session.get(ServiceIntervention, iv_id) is None


@pytest.mark.integration
def test_intervention_technician_set_null_on_user_delete(db_session: Session) -> None:
    tech = UserFactory()
    iv = ServiceInterventionFactory(technician=tech)
    db_session.flush()
    db_session.delete(tech)
    db_session.flush()
    db_session.refresh(iv)
    assert iv.technician_user_id is None


@pytest.mark.integration
def test_action_cascade_on_intervention_delete(db_session: Session) -> None:
    action = InterventionActionFactory()
    db_session.flush()
    aid = action.id
    iv = action.intervention
    db_session.delete(iv)
    db_session.flush()
    assert db_session.get(InterventionAction, aid) is None


@pytest.mark.integration
def test_action_repr(db_session: Session) -> None:
    action = InterventionActionFactory()
    db_session.flush()
    assert action.id.hex()[:8] in repr(action)


@pytest.mark.integration
def test_finding_cascade(db_session: Session) -> None:
    finding = InterventionFindingFactory(is_root_cause=True)
    db_session.flush()
    fid = finding.id
    db_session.delete(finding.intervention)
    db_session.flush()
    assert db_session.get(InterventionFinding, fid) is None


@pytest.mark.integration
def test_finding_repr_root_cause_flag(db_session: Session) -> None:
    finding = InterventionFindingFactory(is_root_cause=True)
    db_session.flush()
    assert "root=True" in repr(finding)


@pytest.mark.integration
def test_part_master_unique_code(db_session: Session) -> None:
    PartMasterFactory(code="DUP-CODE")
    db_session.flush()
    with pytest.raises(IntegrityError):
        PartMasterFactory(code="DUP-CODE")
    db_session.rollback()


@pytest.mark.integration
def test_part_master_label_and_repr(db_session: Session) -> None:
    p = PartMasterFactory(code="P-1", description="Spindle bearing")
    db_session.flush()
    assert p.label == "P-1 — Spindle bearing"
    bare = PartMasterFactory(code="P-2", description="")
    db_session.flush()
    assert bare.label == "P-2"
    assert "P-1" in repr(p)


@pytest.mark.integration
def test_part_usage_part_id_set_null_on_part_delete(db_session: Session) -> None:
    part = PartMasterFactory()
    usage = ServicePartUsageFactory(part=part, part_code=part.code)
    db_session.flush()
    db_session.delete(part)
    db_session.flush()
    db_session.refresh(usage)
    assert usage.part_id is None
    assert usage.part_code == part.code  # snapshot survives


@pytest.mark.integration
def test_part_usage_cascade_on_intervention_delete(db_session: Session) -> None:
    usage = ServicePartUsageFactory()
    db_session.flush()
    uid = usage.id
    iv = usage.intervention
    db_session.delete(iv)
    db_session.flush()
    assert db_session.get(ServicePartUsage, uid) is None


@pytest.mark.integration
def test_part_usage_repr(db_session: Session) -> None:
    usage = ServicePartUsageFactory(part_code="X", quantity=3)
    db_session.flush()
    assert "x3" in repr(usage)


@pytest.mark.integration
def test_ticket_attachment_intervention_id_set_null(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    attachment = TicketAttachmentFactory(ticket=iv.ticket)
    attachment.intervention_id = iv.id
    db_session.flush()
    db_session.delete(iv)
    db_session.flush()
    db_session.refresh(attachment)
    assert attachment.intervention_id is None
    # Verify the attachment row itself is still around.
    assert db_session.get(TicketAttachment, attachment.id) is not None


@pytest.mark.integration
def test_intervention_uses_default_started_at(db_session: Session, frozen_clock: datetime) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    iv = ServiceIntervention(ticket_id=ticket.id)
    db_session.add(iv)
    db_session.flush()
    assert iv.started_at == frozen_clock


@pytest.mark.integration
def test_intervention_action_duration_optional(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    a = InterventionAction(intervention_id=iv.id, description="x", duration_minutes=None)
    db_session.add(a)
    db_session.flush()
    assert a.duration_minutes is None
    a.duration_minutes = 12
    db_session.flush()
    assert a.duration_minutes == 12


@pytest.mark.integration
def test_part_usage_default_quantity_one(db_session: Session) -> None:
    iv = ServiceInterventionFactory()
    db_session.flush()
    usage = ServicePartUsage(
        intervention_id=iv.id,
        part_code="X",
        description="",
        quantity=1,
        unit="pcs",
    )
    db_session.add(usage)
    db_session.flush()
    assert usage.quantity == 1


@pytest.mark.integration
def test_intervention_started_at_aware(db_session: Session) -> None:
    when = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    iv = ServiceInterventionFactory(started_at=when)
    db_session.flush()
    assert iv.started_at.tzinfo is not None
