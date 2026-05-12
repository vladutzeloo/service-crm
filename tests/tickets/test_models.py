"""Model-level tests for the tickets domain.

Covers the constraints declared in v0.5:

- ``service_ticket.number`` is unique.
- ``ticket_type.code`` and ``ticket_priority.code`` are unique.
- ``ticket_status_history`` cascades on ticket deletion.
- ``TicketComment``/``TicketAttachment`` cascade on ticket deletion.
- Equipment FK SET NULL when the linked equipment is deleted.
"""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

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
    TicketAttachmentFactory,
    TicketCommentFactory,
    TicketPriorityFactory,
    TicketTypeFactory,
)


@pytest.mark.integration
def test_ticket_type_unique_code(db_session: Session) -> None:
    TicketTypeFactory(code="dup-type-code")
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        TicketTypeFactory(code="dup-type-code")
    db_session.rollback()


@pytest.mark.integration
def test_ticket_priority_unique_code(db_session: Session) -> None:
    TicketPriorityFactory(code="dup-prio-code")
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        TicketPriorityFactory(code="dup-prio-code")
    db_session.rollback()


@pytest.mark.integration
def test_service_ticket_number_unique(db_session: Session) -> None:
    ServiceTicketFactory(number=9999)
    db_session.flush()
    with pytest.raises((IntegrityError, Exception)):
        ServiceTicketFactory(number=9999)
    db_session.rollback()


@pytest.mark.integration
def test_ticket_cascade_deletes_history(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    # The initial history row is written by the audit listener on create.
    hist = TicketStatusHistory(
        ticket_id=ticket.id,
        from_state="new",
        to_state="qualified",
    )
    db_session.add(hist)
    db_session.flush()
    hist_id = hist.id

    db_session.delete(ticket)
    db_session.flush()

    assert db_session.get(TicketStatusHistory, hist_id) is None


@pytest.mark.integration
def test_ticket_cascade_deletes_comments_and_attachments(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    c = TicketCommentFactory(ticket=ticket)
    a = TicketAttachmentFactory(ticket=ticket)
    db_session.flush()
    cid, aid = c.id, a.id

    db_session.delete(ticket)
    db_session.flush()

    assert db_session.get(TicketComment, cid) is None
    assert db_session.get(TicketAttachment, aid) is None


@pytest.mark.integration
def test_equipment_delete_sets_ticket_equipment_id_null(db_session: Session) -> None:
    client = ClientFactory()
    eq = EquipmentFactory(client=client)
    ticket = ServiceTicketFactory(client=client, equipment=eq)
    db_session.flush()
    tid = ticket.id

    db_session.delete(eq)
    db_session.flush()
    db_session.expire(ticket)

    refreshed = db_session.get(ServiceTicket, tid)
    assert refreshed is not None
    assert refreshed.equipment_id is None


@pytest.mark.integration
def test_client_delete_cascades_tickets(db_session: Session) -> None:
    client = ClientFactory()
    ticket = ServiceTicketFactory(client=client)
    db_session.flush()
    tid = ticket.id

    db_session.delete(client)
    db_session.flush()
    db_session.expire_all()

    assert db_session.get(ServiceTicket, tid) is None


@pytest.mark.integration
def test_ticket_label_is_padded(db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=42)
    db_session.flush()
    assert ticket.label == "T-000042"


@pytest.mark.integration
def test_ticket_status_enum_helper(db_session: Session) -> None:
    ticket = ServiceTicketFactory(status=TicketStatus.IN_PROGRESS.value)
    db_session.flush()
    assert ticket.status_enum is TicketStatus.IN_PROGRESS


@pytest.mark.integration
def test_ticket_is_terminal_helper(db_session: Session) -> None:
    closed = ServiceTicketFactory(status=TicketStatus.CLOSED.value)
    cancelled = ServiceTicketFactory(status=TicketStatus.CANCELLED.value)
    open_t = ServiceTicketFactory(status=TicketStatus.NEW.value)
    db_session.flush()
    assert closed.is_terminal is True
    assert cancelled.is_terminal is True
    assert open_t.is_terminal is False


@pytest.mark.integration
def test_ticket_creation_writes_initial_history(db_session: Session) -> None:
    """The audit listener writes a from_state=NULL history row on insert."""
    ticket = ServiceTicketFactory()
    db_session.flush()
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .all()
    )
    assert len(rows) == 1
    assert rows[0].from_state is None
    assert rows[0].to_state == TicketStatus.NEW.value


@pytest.mark.integration
def test_ticket_status_mutation_writes_history(db_session: Session) -> None:
    """Mutating ``ticket.status`` directly still writes history."""
    ticket = ServiceTicketFactory(status=TicketStatus.NEW.value)
    db_session.flush()
    ticket.status = TicketStatus.QUALIFIED.value
    db_session.flush()
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .order_by(TicketStatusHistory.occurred_at)
        .all()
    )
    # Initial creation row + the new transition row.
    assert len(rows) == 2
    assert rows[1].from_state == TicketStatus.NEW.value
    assert rows[1].to_state == TicketStatus.QUALIFIED.value


@pytest.mark.integration
def test_unchanged_ticket_does_not_write_history(db_session: Session) -> None:
    ticket = ServiceTicketFactory()
    db_session.flush()
    # Update a non-status column; no extra history row should appear.
    ticket.title = "renamed"
    db_session.flush()
    rows = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .all()
    )
    assert len(rows) == 1


@pytest.mark.integration
def test_lookup_display_label_falls_back_outside_request(db_session: Session) -> None:
    """``display_label`` is safe to call without a request context.

    Outside of a request, ``flask_babel`` can't resolve the locale, so
    the property falls back to the stored ``label`` then to ``code``.
    """
    t = db_session.query(TicketType).filter(TicketType.code == "incident").one()
    assert t.display_label in {"Incident", "incident"}
    p = db_session.query(TicketPriority).filter(TicketPriority.code == "normal").one()
    assert p.display_label in {"Normal", "normal"}


@pytest.mark.integration
def test_lookup_display_label_translates_inside_request(
    db_session: Session,
) -> None:
    """Inside a request context the translation registry returns the
    localised string (``"Incident"`` for ``"incident"``)."""
    from flask import current_app

    with current_app.test_request_context("/?lang=en"):
        t = db_session.query(TicketType).filter(TicketType.code == "incident").one()
        assert t.display_label == "Incident"
        p = (
            db_session.query(TicketPriority).filter(TicketPriority.code == "normal").one()
        )
        assert p.display_label == "Normal"


@pytest.mark.integration
def test_lookup_display_label_unknown_code_falls_back(db_session: Session) -> None:
    t = TicketTypeFactory(code="zzz-novel", label="Custom Label")
    db_session.flush()
    assert t.display_label == "Custom Label"

    p = TicketPriorityFactory(code="zzz-prio-novel", label="")
    db_session.flush()
    assert p.display_label == "zzz-prio-novel"


@pytest.mark.integration
def test_lookup_default_seeds(db_session: Session) -> None:
    default_type = (
        db_session.query(TicketType).filter(TicketType.is_default.is_(True)).one()
    )
    default_prio = (
        db_session.query(TicketPriority).filter(TicketPriority.is_default.is_(True)).one()
    )
    assert default_type.code == "incident"
    assert default_prio.code == "normal"


@pytest.mark.integration
def test_model_reprs(db_session: Session) -> None:
    ticket = ServiceTicketFactory(number=7)
    c = TicketCommentFactory(ticket=ticket)
    a = TicketAttachmentFactory(ticket=ticket, filename="REPR.pdf")
    db_session.flush()
    t = db_session.query(TicketType).filter(TicketType.code == "incident").one()
    p = db_session.query(TicketPriority).filter(TicketPriority.code == "normal").one()
    h = (
        db_session.query(TicketStatusHistory)
        .filter(TicketStatusHistory.ticket_id == ticket.id)
        .first()
    )
    assert h is not None
    assert "T-000007" in repr(ticket)
    assert "incident" in repr(t)
    assert "normal" in repr(p)
    assert c.id.hex()[:8] in repr(c)
    assert "REPR.pdf" in repr(a)
    assert "→" in repr(h)
