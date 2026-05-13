"""Service-layer tests for the knowledge blueprint.

Includes the frozen-snapshot property test required by ROADMAP §0.6.0:
editing a template after a run has been started never mutates the
historical run.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy.orm import Session

from service_crm.knowledge import services
from service_crm.knowledge.models import (
    ChecklistTemplateItem,
    ProcedureDocument,
)
from tests.factories import (
    ChecklistTemplateFactory,
    ChecklistTemplateItemFactory,
    ProcedureDocumentFactory,
    ProcedureTagFactory,
    ServiceInterventionFactory,
)

# ── Templates ────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_templates_active_only(db_session: Session) -> None:
    ChecklistTemplateFactory(name="LIST-A", is_active=True)
    ChecklistTemplateFactory(name="LIST-B", is_active=False)
    db_session.flush()
    actives = services.list_templates(db_session)
    names = {t.name for t in actives if t.name.startswith("LIST-")}
    assert names == {"LIST-A"}
    all_t = services.list_templates(db_session, active_only=False)
    names = {t.name for t in all_t if t.name.startswith("LIST-")}
    assert names == {"LIST-A", "LIST-B"}


@pytest.mark.integration
def test_require_template_bad_hex(db_session: Session) -> None:
    with pytest.raises(ValueError, match="invalid"):
        services.require_template(db_session, "zz")


@pytest.mark.integration
def test_require_template_missing(db_session: Session) -> None:
    with pytest.raises(ValueError, match="not found"):
        services.require_template(db_session, "00" * 16)


@pytest.mark.integration
def test_create_template_happy(db_session: Session) -> None:
    tpl = services.create_template(db_session, name="Spindle", description="Service spindle")
    assert tpl.name == "Spindle"


@pytest.mark.integration
def test_create_template_validations(db_session: Session) -> None:
    with pytest.raises(ValueError, match="template name"):
        services.create_template(db_session, name="")
    services.create_template(db_session, name="Same")
    with pytest.raises(ValueError, match="already exists"):
        services.create_template(db_session, name="SAME")


@pytest.mark.integration
def test_update_template(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    services.update_template(
        db_session,
        tpl,
        name="renamed",
        description="d",
        is_active=False,
    )
    assert tpl.name == "renamed"
    assert tpl.is_active is False
    with pytest.raises(ValueError, match="template name"):
        services.update_template(db_session, tpl, name="", description="", is_active=True)


@pytest.mark.integration
def test_add_template_item_happy(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    item = services.add_template_item(
        db_session,
        template_id=tpl.id,
        key="step1",
        label="Step 1",
        kind="bool",
        is_required=True,
    )
    assert item.position == 0
    item2 = services.add_template_item(
        db_session,
        template_id=tpl.id,
        key="step2",
        label="Step 2",
        kind="text",
    )
    assert item2.position == 1


@pytest.mark.integration
def test_add_template_item_choice_requires_options(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="at least one option"):
        services.add_template_item(
            db_session,
            template_id=tpl.id,
            key="s",
            label="s",
            kind="choice",
        )
    item = services.add_template_item(
        db_session,
        template_id=tpl.id,
        key="s2",
        label="s2",
        kind="choice",
        choice_options=["a", "b"],
    )
    assert item.choice_options == ["a", "b"]


@pytest.mark.integration
def test_add_template_item_validations(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="item key"):
        services.add_template_item(db_session, template_id=tpl.id, key="", label="x", kind="bool")
    with pytest.raises(ValueError, match="item label"):
        services.add_template_item(db_session, template_id=tpl.id, key="x", label="", kind="bool")
    with pytest.raises(ValueError, match="unknown kind"):
        services.add_template_item(db_session, template_id=tpl.id, key="x", label="x", kind="bogus")
    with pytest.raises(ValueError, match="template not found"):
        services.add_template_item(
            db_session, template_id=b"\x09" * 16, key="x", label="x", kind="bool"
        )


@pytest.mark.integration
def test_add_template_item_duplicate_key(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    services.add_template_item(db_session, template_id=tpl.id, key="dup", label="A", kind="bool")
    with pytest.raises(ValueError, match="already exists"):
        services.add_template_item(
            db_session, template_id=tpl.id, key="dup", label="B", kind="bool"
        )


@pytest.mark.integration
def test_add_template_item_explicit_position(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    item = services.add_template_item(
        db_session,
        template_id=tpl.id,
        key="x",
        label="x",
        kind="bool",
        position=7,
    )
    assert item.position == 7


@pytest.mark.integration
def test_require_template_item_and_delete(db_session: Session) -> None:
    item = ChecklistTemplateItemFactory()
    db_session.flush()
    got = services.require_template_item(db_session, item.id.hex())
    assert got is item
    with pytest.raises(ValueError, match="invalid"):
        services.require_template_item(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        services.require_template_item(db_session, "00" * 16)
    services.delete_template_item(db_session, item)
    assert db_session.get(ChecklistTemplateItem, item.id) is None


# ── Checklist runs ───────────────────────────────────────────────────────────


@pytest.mark.integration
def test_start_checklist_run_freezes_template(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory(name="Probe")
    ChecklistTemplateItemFactory(template=tpl, position=0, key="t1", label="T1", kind="bool")
    ChecklistTemplateItemFactory(template=tpl, position=1, key="t2", label="T2", kind="text")
    db_session.flush()
    iv = ServiceInterventionFactory()
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=iv.id)
    assert run.snapshot["name"] == "Probe"
    assert len(run.snapshot["items"]) == 2
    assert len(run.items) == 2
    # Now mutate the template — run.snapshot and run.items must stay put.
    services.update_template(db_session, tpl, name="Renamed", description="", is_active=True)
    for it in tpl.items:
        services.delete_template_item(db_session, it)
    db_session.flush()
    db_session.refresh(run)
    assert run.snapshot["name"] == "Probe"
    assert run.items, "run items survived template item deletion"


@pytest.mark.integration
def test_start_checklist_run_unknown_template(db_session: Session) -> None:
    with pytest.raises(ValueError, match="template not found"):
        services.start_checklist_run(db_session, template_id=b"\xff" * 16, intervention_id=None)


@pytest.mark.integration
def test_start_checklist_run_unknown_intervention(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    with pytest.raises(ValueError, match="intervention not found"):
        services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=b"\xff" * 16)


@pytest.mark.integration
def test_answer_run_item_kinds(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    ChecklistTemplateItemFactory(template=tpl, key="b", kind="bool")
    ChecklistTemplateItemFactory(template=tpl, key="n", kind="number")
    ChecklistTemplateItemFactory(template=tpl, key="t", kind="text")
    ChecklistTemplateItemFactory(template=tpl, key="c", kind="choice")
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=None)
    by_key = {it.key: it for it in run.items}
    services.answer_run_item(db_session, by_key["b"], answer=True)
    assert by_key["b"].answer is True
    services.answer_run_item(db_session, by_key["b"], answer="yes")
    assert by_key["b"].answer is True
    services.answer_run_item(db_session, by_key["b"], answer="no")
    assert by_key["b"].answer is False
    services.answer_run_item(db_session, by_key["n"], answer="42.5")
    assert by_key["n"].answer == 42.5
    services.answer_run_item(db_session, by_key["t"], answer="hello", notes="ok")
    assert by_key["t"].answer == "hello"
    assert by_key["t"].notes == "ok"
    services.answer_run_item(db_session, by_key["c"], answer="a")
    assert by_key["c"].answer == "a"
    # Clearing
    services.answer_run_item(db_session, by_key["t"], answer="")
    assert by_key["t"].answer is None
    services.answer_run_item(db_session, by_key["n"], answer=None)
    assert by_key["n"].answer is None
    # Number type-mismatch
    with pytest.raises(ValueError, match="must be a number"):
        services.answer_run_item(db_session, by_key["n"], answer="abc")


@pytest.mark.integration
def test_answer_run_item_bool_truthy_int(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    ChecklistTemplateItemFactory(template=tpl, key="b", kind="bool")
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=None)
    by_key = {it.key: it for it in run.items}
    services.answer_run_item(db_session, by_key["b"], answer=1)
    assert by_key["b"].answer is True


@pytest.mark.integration
def test_require_run(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=None)
    assert services.require_run(db_session, run.id.hex()) is run
    with pytest.raises(ValueError, match="invalid"):
        services.require_run(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        services.require_run(db_session, "00" * 16)


@pytest.mark.integration
def test_complete_run(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    ChecklistTemplateItemFactory(template=tpl, key="b", kind="bool", is_required=True)
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=None)
    by_key = {it.key: it for it in run.items}
    with pytest.raises(ValueError, match="required"):
        services.complete_run(db_session, run)
    services.answer_run_item(db_session, by_key["b"], answer=True)
    services.complete_run(db_session, run)
    assert run.is_completed is True


@pytest.mark.integration
def test_complete_run_explicit_when(db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    run = services.start_checklist_run(db_session, template_id=tpl.id, intervention_id=None)
    when = datetime(2026, 5, 13, 10, 30, tzinfo=UTC)
    services.complete_run(db_session, run, when=when)
    assert run.completed_at == when


# ── Tags ─────────────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_tags_active(db_session: Session) -> None:
    ProcedureTagFactory(code="ACT-A", is_active=True)
    ProcedureTagFactory(code="ACT-B", is_active=False)
    db_session.flush()

    def _codes(items: list) -> set[str]:
        return {t.code for t in items if t.code.startswith("ACT-")}

    assert _codes(services.list_tags(db_session)) == {"ACT-A"}
    assert _codes(services.list_tags(db_session, active_only=False)) == {
        "ACT-A",
        "ACT-B",
    }


@pytest.mark.integration
def test_require_tag(db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    assert services.require_tag(db_session, tag.id.hex()) is tag
    with pytest.raises(ValueError, match="invalid"):
        services.require_tag(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        services.require_tag(db_session, "00" * 16)


@pytest.mark.integration
def test_create_tag_validations(db_session: Session) -> None:
    with pytest.raises(ValueError, match="tag code"):
        services.create_tag(db_session, code="", name="x")
    with pytest.raises(ValueError, match="tag name"):
        services.create_tag(db_session, code="x", name="")
    services.create_tag(db_session, code="abc", name="A")
    with pytest.raises(ValueError, match="already exists"):
        services.create_tag(db_session, code="ABC", name="B")


@pytest.mark.integration
def test_update_tag(db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    services.update_tag(db_session, tag, name="new", is_active=False)
    assert tag.name == "new"
    with pytest.raises(ValueError, match="tag name"):
        services.update_tag(db_session, tag, name="", is_active=True)


# ── Procedures ───────────────────────────────────────────────────────────────


@pytest.mark.integration
def test_list_procedures_basic(db_session: Session) -> None:
    a = ProcedureDocumentFactory(title="Spindle bearing service")
    ProcedureDocumentFactory(title="Hose clamps", is_active=False)
    db_session.flush()

    def _titles(items: list) -> set[str]:
        return {d.title for d in items}

    items = services.list_procedures(db_session, q="spindle")
    assert items[0].title == a.title
    all_active = services.list_procedures(db_session)
    assert "Hose clamps" not in _titles(all_active)
    all_docs = services.list_procedures(db_session, active_only=False)
    assert "Hose clamps" in _titles(all_docs)


@pytest.mark.integration
def test_list_procedures_filter_by_tag(db_session: Session) -> None:
    tag = ProcedureTagFactory()
    doc_with = ProcedureDocumentFactory()
    doc_without = ProcedureDocumentFactory()
    doc_with.tags = [tag]
    db_session.flush()
    items = services.list_procedures(db_session, tag_ids=[tag.id])
    assert doc_with in items
    assert doc_without not in items


@pytest.mark.integration
def test_require_procedure(db_session: Session) -> None:
    d = ProcedureDocumentFactory()
    db_session.flush()
    assert services.require_procedure(db_session, d.id.hex()) is d
    with pytest.raises(ValueError, match="invalid"):
        services.require_procedure(db_session, "zz")
    with pytest.raises(ValueError, match="not found"):
        services.require_procedure(db_session, "00" * 16)


@pytest.mark.integration
def test_create_procedure_happy(db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    doc = services.create_procedure(
        db_session,
        title="How to align spindle",
        summary="five steps",
        body="# Step 1\nDo X.",
        tag_ids=[tag.id],
    )
    assert doc.title == "How to align spindle"
    assert tag in doc.tags


@pytest.mark.integration
def test_create_procedure_validations(db_session: Session) -> None:
    with pytest.raises(ValueError, match="title"):
        services.create_procedure(db_session, title="")
    with pytest.raises(ValueError, match="body exceeds"):
        services.create_procedure(
            db_session,
            title="X",
            body="x" * (ProcedureDocument.BODY_MAX_BYTES + 1),
        )


@pytest.mark.integration
def test_create_procedure_unknown_tag(db_session: Session) -> None:
    with pytest.raises(ValueError, match="unknown tag id"):
        services.create_procedure(db_session, title="X", tag_ids=[b"\x07" * 16])


@pytest.mark.integration
def test_update_procedure(db_session: Session) -> None:
    tag1 = ProcedureTagFactory()
    tag2 = ProcedureTagFactory()
    doc = ProcedureDocumentFactory()
    doc.tags = [tag1]
    db_session.flush()
    services.update_procedure(
        db_session,
        doc,
        title="new",
        summary="s",
        body="b",
        tag_ids=[tag2.id],
        is_active=False,
    )
    assert doc.title == "new"
    assert doc.tags == [tag2]
    assert doc.is_active is False
    with pytest.raises(ValueError, match="title"):
        services.update_procedure(
            db_session,
            doc,
            title="",
            summary="",
            body="",
            tag_ids=[],
            is_active=True,
        )
    with pytest.raises(ValueError, match="body exceeds"):
        services.update_procedure(
            db_session,
            doc,
            title="x",
            summary="",
            body="x" * (ProcedureDocument.BODY_MAX_BYTES + 1),
            tag_ids=[],
            is_active=True,
        )


@pytest.mark.integration
def test_procedure_search_filter_postgres_branch(monkeypatch) -> None:
    monkeypatch.setattr("service_crm.knowledge.services._dialect", lambda: "postgresql")
    flt = services._procedure_search_filter("hello")
    assert flt is not None
    assert "to_tsvector" in str(flt.compile(compile_kwargs={"literal_binds": True}))


@pytest.mark.integration
def test_update_procedure_clears_tags_on_empty(db_session: Session) -> None:
    tag = ProcedureTagFactory()
    doc = ProcedureDocumentFactory()
    doc.tags = [tag]
    db_session.flush()
    services.update_procedure(
        db_session,
        doc,
        title="x",
        summary="",
        body="",
        tag_ids=None,
        is_active=True,
    )
    assert doc.tags == []
