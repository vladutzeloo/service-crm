"""Model-level tests for the planning blueprint."""

from __future__ import annotations

from datetime import date

import pytest
from sqlalchemy.exc import IntegrityError

from service_crm.planning.models import (
    TechnicianAssignment,
    TechnicianCapacitySlot,
)
from tests.factories import (
    ServiceInterventionFactory,
    ServiceTicketFactory,
    TechnicianAssignmentFactory,
    TechnicianCapacitySlotFactory,
    TechnicianFactory,
    UserFactory,
)


def test_technician_unique_user(db_session):
    user = UserFactory()
    TechnicianFactory(user=user)
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        TechnicianFactory(user=user)
    db_session.rollback()


def test_technician_label_falls_back_to_email(db_session):
    user = UserFactory(email="tech@example.com")
    tech = TechnicianFactory(user=user, display_name="")
    db_session.flush()
    assert tech.label == "tech@example.com"


def test_technician_label_prefers_display_name(db_session):
    tech = TechnicianFactory(display_name="Alice")
    db_session.flush()
    assert tech.label == "Alice"


def test_technician_repr_round_trip(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    assert "Technician" in repr(tech)


def test_capacity_slot_unique_day(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    TechnicianCapacitySlotFactory(technician=tech, day=date(2026, 6, 1))
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        TechnicianCapacitySlotFactory(technician=tech, day=date(2026, 6, 1))
    db_session.rollback()


def test_capacity_slot_non_negative(db_session):
    with pytest.raises(IntegrityError):
        TechnicianCapacitySlotFactory(capacity_minutes=-1)
    db_session.rollback()


def test_capacity_slot_repr(db_session):
    slot = TechnicianCapacitySlotFactory()
    db_session.flush()
    assert "TechnicianCapacitySlot" in repr(slot)


def test_assignment_requires_target(db_session):
    tech = TechnicianFactory()
    db_session.flush()
    with pytest.raises(IntegrityError):
        TechnicianAssignmentFactory(technician=tech, ticket=None, intervention=None)
    db_session.rollback()


def test_assignment_allows_ticket_only(db_session):
    tech = TechnicianFactory()
    ticket = ServiceTicketFactory()
    asg = TechnicianAssignmentFactory(technician=tech, ticket=ticket, intervention=None)
    db_session.flush()
    assert asg.ticket_id == ticket.id
    assert asg.intervention_id is None


def test_assignment_allows_intervention_only(db_session):
    tech = TechnicianFactory()
    intervention = ServiceInterventionFactory()
    asg = TechnicianAssignmentFactory(technician=tech, ticket=None, intervention=intervention)
    db_session.flush()
    assert asg.intervention_id == intervention.id
    assert asg.ticket_id is None


def test_assignment_allows_both(db_session):
    tech = TechnicianFactory()
    ticket = ServiceTicketFactory()
    intervention = ServiceInterventionFactory(ticket=ticket)
    asg = TechnicianAssignmentFactory(technician=tech, ticket=ticket, intervention=intervention)
    db_session.flush()
    assert asg.ticket_id == ticket.id
    assert asg.intervention_id == intervention.id


def test_assignment_repr_round_trip(db_session):
    asg = TechnicianAssignmentFactory()
    db_session.flush()
    assert "TechnicianAssignment" in repr(asg)


def test_capacity_slot_cascades_when_tech_deleted(db_session):
    tech = TechnicianFactory()
    slot = TechnicianCapacitySlotFactory(technician=tech)
    db_session.flush()
    db_session.delete(tech)
    db_session.flush()
    assert db_session.get(TechnicianCapacitySlot, slot.id) is None


def test_assignment_cascades_when_tech_deleted(db_session):
    tech = TechnicianFactory()
    asg = TechnicianAssignmentFactory(technician=tech)
    db_session.flush()
    db_session.delete(tech)
    db_session.flush()
    assert db_session.get(TechnicianAssignment, asg.id) is None
