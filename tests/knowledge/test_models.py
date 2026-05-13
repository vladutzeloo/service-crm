"""Model-level tests for the knowledge blueprint."""

from __future__ import annotations

import pytest
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from service_crm.knowledge.models import (
    ChecklistRun,
    ChecklistRunItem,
    ChecklistTemplateItem,
)
from tests.factories import (
    ChecklistRunFactory,
    ChecklistRunItemFactory,
    ChecklistTemplateFactory,
    ChecklistTemplateItemFactory,
    ProcedureDocumentFactory,
    ProcedureTagFactory,
)


@pytest.mark.integration
def test_checklist_template_unique_name(db_session: Session) -> None:
    ChecklistTemplateFactory(name="UNIQUE-NAME")
    db_session.flush()
    with pytest.raises(IntegrityError):
        ChecklistTemplateFactory(name="UNIQUE-NAME")
    db_session.rollback()


@pytest.mark.integration
def test_checklist_template_repr(db_session: Session) -> None:
    t = ChecklistTemplateFactory(name="X")
    db_session.flush()
    assert "X" in repr(t)


@pytest.mark.integration
def test_template_item_cascade_on_template_delete(db_session: Session) -> None:
    item = ChecklistTemplateItemFactory()
    db_session.flush()
    iid = item.id
    db_session.delete(item.template)
    db_session.flush()
    assert db_session.get(ChecklistTemplateItem, iid) is None


@pytest.mark.integration
def test_template_item_unique_key_per_template(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    ChecklistTemplateItemFactory(template=tpl, key="check_a")
    db_session.flush()
    with pytest.raises(IntegrityError):
        ChecklistTemplateItemFactory(template=tpl, key="check_a")
    db_session.rollback()


@pytest.mark.integration
def test_template_item_repr(db_session: Session) -> None:
    item = ChecklistTemplateItemFactory(key="check_a", kind="bool")
    db_session.flush()
    assert "check_a" in repr(item)
    assert "kind=bool" in repr(item)


@pytest.mark.integration
def test_checklist_run_title_from_snapshot(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory(name="The Check")
    run = ChecklistRunFactory(template=tpl)
    db_session.flush()
    assert run.title == "The Check"


@pytest.mark.integration
def test_checklist_run_title_fallback(db_session: Session) -> None:
    run = ChecklistRunFactory()
    run.snapshot = {}
    db_session.flush()
    assert run.title == "(checklist)"
    run.snapshot = "not a dict"  # type: ignore[assignment]
    db_session.flush()
    assert run.title == "(checklist)"


@pytest.mark.integration
def test_checklist_run_repr(db_session: Session) -> None:
    run = ChecklistRunFactory()
    db_session.flush()
    rep = repr(run)
    assert "ChecklistRun" in rep
    assert "completed=False" in rep


@pytest.mark.integration
def test_checklist_run_is_completed(db_session: Session) -> None:
    from datetime import UTC, datetime

    run = ChecklistRunFactory()
    db_session.flush()
    assert run.is_completed is False
    run.completed_at = datetime(2026, 5, 13, 10, 0, tzinfo=UTC)
    db_session.flush()
    assert run.is_completed is True


@pytest.mark.integration
def test_checklist_run_cascade_on_intervention_delete(db_session: Session) -> None:
    from tests.factories import ServiceInterventionFactory

    iv = ServiceInterventionFactory()
    run = ChecklistRunFactory(intervention=iv)
    db_session.flush()
    rid = run.id
    db_session.delete(iv)
    db_session.flush()
    assert db_session.get(ChecklistRun, rid) is None


@pytest.mark.integration
def test_checklist_run_template_set_null_on_template_delete(
    db_session: Session,
) -> None:
    tpl = ChecklistTemplateFactory()
    run = ChecklistRunFactory(template=tpl)
    db_session.flush()
    db_session.delete(tpl)
    db_session.flush()
    db_session.refresh(run)
    assert run.template_id is None


@pytest.mark.integration
def test_checklist_run_item_repr_and_is_answered(db_session: Session) -> None:
    item = ChecklistRunItemFactory(key="probe_check")
    db_session.flush()
    assert "probe_check" in repr(item)
    assert item.is_answered is False
    item.answer = True
    db_session.flush()
    assert item.is_answered is True


@pytest.mark.integration
def test_checklist_run_item_cascade_on_run_delete(db_session: Session) -> None:
    item = ChecklistRunItemFactory()
    db_session.flush()
    iid = item.id
    db_session.delete(item.run)
    db_session.flush()
    assert db_session.get(ChecklistRunItem, iid) is None


@pytest.mark.integration
def test_procedure_tag_unique_code(db_session: Session) -> None:
    ProcedureTagFactory(code="dup-tag")
    db_session.flush()
    with pytest.raises(IntegrityError):
        ProcedureTagFactory(code="dup-tag")
    db_session.rollback()


@pytest.mark.integration
def test_procedure_tag_repr(db_session: Session) -> None:
    t = ProcedureTagFactory(code="x")
    db_session.flush()
    assert "x" in repr(t)


@pytest.mark.integration
def test_procedure_document_repr(db_session: Session) -> None:
    d = ProcedureDocumentFactory(title="Hello")
    db_session.flush()
    assert "Hello" in repr(d)


@pytest.mark.integration
def test_procedure_document_tag_m2m(db_session: Session) -> None:
    doc = ProcedureDocumentFactory()
    t1 = ProcedureTagFactory()
    t2 = ProcedureTagFactory()
    doc.tags = [t1, t2]
    db_session.flush()
    assert set(doc.tags) == {t1, t2}
    assert doc in t1.documents
    # Cascade on doc delete clears the M2M.
    db_session.delete(doc)
    db_session.flush()
    db_session.refresh(t1)
    assert all(d.id != doc.id for d in t1.documents)
