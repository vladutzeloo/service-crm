"""E2E tests for the knowledge blueprint routes."""

from __future__ import annotations

import uuid

import pytest
from flask.testing import FlaskClient
from sqlalchemy.orm import Session

from service_crm.knowledge.models import (
    ChecklistTemplate,
    ChecklistTemplateItem,
    ProcedureDocument,
    ProcedureTag,
)
from tests.factories import (
    ChecklistTemplateFactory,
    ChecklistTemplateItemFactory,
    ProcedureDocumentFactory,
    ProcedureTagFactory,
)


def _tok() -> str:
    return uuid.uuid4().hex


# ── Auth gate ───────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_procedures_list_requires_login(client: FlaskClient) -> None:
    resp = client.get("/knowledge/procedures", follow_redirects=False)
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


# ── Index redirect ──────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_index_redirects_to_procedures(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/", follow_redirects=False)
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/knowledge/procedures")


# ── Procedure list / detail / new / edit ────────────────────────────────────


@pytest.mark.e2e
def test_procedures_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ProcedureDocumentFactory(title="Visible-Procedure-XYZ")
    db_session.flush()
    resp = client_logged_in.get("/knowledge/procedures")
    assert resp.status_code == 200
    assert b"Visible-Procedure-XYZ" in resp.data


@pytest.mark.e2e
def test_procedures_list_with_search(client_logged_in: FlaskClient, db_session: Session) -> None:
    ProcedureDocumentFactory(title="SearchUniqueAAA")
    ProcedureDocumentFactory(title="OtherBBB")
    db_session.flush()
    resp = client_logged_in.get("/knowledge/procedures?q=SearchUniqueAAA")
    assert b"SearchUniqueAAA" in resp.data
    assert b"OtherBBB" not in resp.data


@pytest.mark.e2e
def test_procedures_list_filter_by_tag(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory()
    matched = ProcedureDocumentFactory(title="TaggedDoc")
    matched.tags = [tag]
    ProcedureDocumentFactory(title="UntaggedDoc")
    db_session.flush()
    resp = client_logged_in.get(f"/knowledge/procedures?tag={tag.id.hex()}")
    assert b"TaggedDoc" in resp.data
    assert b"UntaggedDoc" not in resp.data


@pytest.mark.e2e
def test_procedures_list_with_show_all(client_logged_in: FlaskClient, db_session: Session) -> None:
    ProcedureDocumentFactory(title="InactiveSpecialAAA", is_active=False)
    db_session.flush()
    resp = client_logged_in.get("/knowledge/procedures")
    assert b"InactiveSpecialAAA" not in resp.data
    resp = client_logged_in.get("/knowledge/procedures?show=all")
    assert b"InactiveSpecialAAA" in resp.data


@pytest.mark.e2e
def test_procedures_list_ignores_bad_tag_hex(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.get("/knowledge/procedures?tag=zz&tag=abc")
    # Bad hex ignored; route still renders.
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_detail_happy(client_logged_in: FlaskClient, db_session: Session) -> None:
    doc = ProcedureDocumentFactory(title="Doc1", body="# H\nbody")
    db_session.flush()
    resp = client_logged_in.get(f"/knowledge/procedures/{doc.id.hex()}")
    assert resp.status_code == 200
    assert b"Doc1" in resp.data
    assert b"<h1>H</h1>" in resp.data


@pytest.mark.e2e
def test_procedure_detail_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/procedures/zz", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_procedure_new_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    resp = client_logged_in.get("/knowledge/procedures/new")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        "/knowledge/procedures/new",
        data={
            "csrf_token": "x",
            "title": "New Procedure",
            "summary": "s",
            "body": "# heading",
            "tags": [tag.id.hex()],
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    doc = db_session.query(ProcedureDocument).filter_by(title="New Procedure").one()
    assert tag in doc.tags


@pytest.mark.e2e
def test_procedure_new_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "title": "IdempotentProc",
        "summary": "",
        "body": "",
        "tags": [],
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/procedures/new", data=payload)
    client_logged_in.post("/knowledge/procedures/new", data=payload)
    count = db_session.query(ProcedureDocument).filter_by(title="IdempotentProc").count()
    assert count == 1


@pytest.mark.e2e
def test_procedure_new_validation_error(
    client_logged_in: FlaskClient,
) -> None:
    # Empty title triggers service-layer ValueError → re-renders form.
    resp = client_logged_in.post(
        "/knowledge/procedures/new",
        data={
            "csrf_token": "x",
            "title": " ",
            "summary": "",
            "body": "",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    doc = ProcedureDocumentFactory(title="Old")
    db_session.flush()
    resp = client_logged_in.get(f"/knowledge/procedures/{doc.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/knowledge/procedures/{doc.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "title": "Renamed",
            "summary": "s",
            "body": "b",
            "tags": [],
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(doc)
    assert doc.title == "Renamed"


@pytest.mark.e2e
def test_procedure_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/procedures/zz/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_procedure_edit_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    doc = ProcedureDocumentFactory(title="OrigTitle")
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "title": "FirstChange",
        "summary": "",
        "body": "",
        "tags": [],
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/procedures/{doc.id.hex()}/edit", data=payload)
    payload["title"] = "SecondChange"
    client_logged_in.post(f"/knowledge/procedures/{doc.id.hex()}/edit", data=payload)
    db_session.refresh(doc)
    assert doc.title == "FirstChange"


@pytest.mark.e2e
def test_procedure_edit_validation_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    doc = ProcedureDocumentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/procedures/{doc.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "title": " ",
            "summary": "",
            "body": "",
            "tags": [],
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


# ── Tag list / new / edit ───────────────────────────────────────────────────


@pytest.mark.e2e
def test_tags_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ProcedureTagFactory(code="VISIBLE-TAG-AAA", name="visible name AAA")
    db_session.flush()
    resp = client_logged_in.get("/knowledge/tags")
    assert b"VISIBLE-TAG-AAA" in resp.data


@pytest.mark.e2e
def test_tag_new_and_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "code": "newtag",
        "name": "New tag",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/tags/new", data=payload)
    client_logged_in.post("/knowledge/tags/new", data=payload)
    count = db_session.query(ProcedureTag).filter_by(code="newtag").count()
    assert count == 1


@pytest.mark.e2e
def test_tag_new_validation_error(client_logged_in: FlaskClient) -> None:
    # Empty service-layer-rejected name on POST.
    resp = client_logged_in.post(
        "/knowledge/tags/new",
        data={
            "csrf_token": "x",
            "code": "x",
            "name": "Valid",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
    )
    assert resp.status_code == 302
    # Re-submit duplicate code triggers ValueError + flash.
    resp = client_logged_in.post(
        "/knowledge/tags/new",
        data={
            "csrf_token": "x",
            "code": "x",
            "name": "Other",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_tag_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    resp = client_logged_in.get(f"/knowledge/tags/{tag.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/knowledge/tags/{tag.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "name": "RenamedTag",
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(tag)
    assert tag.name == "RenamedTag"


@pytest.mark.e2e
def test_tag_edit_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory(name="Orig")
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "First",
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/tags/{tag.id.hex()}/edit", data=payload)
    payload["name"] = "Second"
    client_logged_in.post(f"/knowledge/tags/{tag.id.hex()}/edit", data=payload)
    db_session.refresh(tag)
    assert tag.name == "First"


@pytest.mark.e2e
def test_tag_edit_validation_error(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/tags/{tag.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "name": " ",
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_tag_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/tags/zz/edit", follow_redirects=False)
    assert resp.status_code == 302


# ── Templates ──────────────────────────────────────────────────────────────


@pytest.mark.e2e
def test_templates_list_renders(client_logged_in: FlaskClient, db_session: Session) -> None:
    ChecklistTemplateFactory(name="VisibleTemplateAAA")
    db_session.flush()
    resp = client_logged_in.get("/knowledge/templates")
    assert b"VisibleTemplateAAA" in resp.data


@pytest.mark.e2e
def test_template_new_get_and_post(client_logged_in: FlaskClient, db_session: Session) -> None:
    resp = client_logged_in.get("/knowledge/templates/new")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        "/knowledge/templates/new",
        data={
            "csrf_token": "x",
            "name": "NewTemplateAAA",
            "description": "x",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.query(ChecklistTemplate).filter_by(name="NewTemplateAAA").count() == 1


@pytest.mark.e2e
def test_template_new_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "IdemTemplateBBB",
        "description": "",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/templates/new", data=payload)
    client_logged_in.post("/knowledge/templates/new", data=payload)
    count = db_session.query(ChecklistTemplate).filter_by(name="IdemTemplateBBB").count()
    assert count == 1


@pytest.mark.e2e
def test_template_new_duplicate_name(client_logged_in: FlaskClient) -> None:
    payload_first = {
        "csrf_token": "x",
        "name": "DupTemplate",
        "description": "",
        "idempotency_token": _tok(),
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/templates/new", data=payload_first)
    resp = client_logged_in.post(
        "/knowledge/templates/new",
        data={**payload_first, "idempotency_token": _tok()},
        follow_redirects=True,
    )
    # Service raised ValueError → re-renders form (200).
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_new_validation_error(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/knowledge/templates/new",
        data={
            "csrf_token": "x",
            "name": " ",
            "description": "",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_edit(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = ChecklistTemplateFactory(name="OrigTpl")
    db_session.flush()
    resp = client_logged_in.get(f"/knowledge/templates/{tpl.id.hex()}/edit")
    assert resp.status_code == 200
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "name": "RenamedTpl",
            "description": "d",
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    db_session.refresh(tpl)
    assert tpl.name == "RenamedTpl"


@pytest.mark.e2e
def test_template_edit_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/templates/zz/edit", follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_edit_idempotent(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = ChecklistTemplateFactory(name="OrigEditTpl")
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "FirstName",
        "description": "",
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/edit", data=payload)
    payload["name"] = "SecondName"
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/edit", data=payload)
    db_session.refresh(tpl)
    assert tpl.name == "FirstName"


@pytest.mark.e2e
def test_template_edit_validation_error(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "name": " ",
            "description": "",
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_template_item_create_and_delete(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items",
        data={
            "csrf_token": "x",
            "key": "step",
            "label": "Step",
            "kind": "bool",
            "is_required": "y",
            "choice_options": "",
            "idempotency_token": _tok(),
            "submit": "Add item",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302
    item = db_session.query(ChecklistTemplateItem).filter_by(template_id=tpl.id).one()
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items/{item.id.hex()}/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert db_session.get(ChecklistTemplateItem, item.id) is None


@pytest.mark.e2e
def test_template_item_create_choice(client_logged_in: FlaskClient, db_session: Session) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items",
        data={
            "csrf_token": "x",
            "key": "choose",
            "label": "Choose",
            "kind": "choice",
            "is_required": "y",
            "choice_options": "a, b, c",
            "idempotency_token": _tok(),
            "submit": "Add item",
        },
    )
    item = db_session.query(ChecklistTemplateItem).filter_by(template_id=tpl.id).one()
    assert item.choice_options == ["a", "b", "c"]


@pytest.mark.e2e
def test_template_item_create_validation_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    # wtforms-level error: empty key
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items",
        data={
            "csrf_token": "x",
            "key": "",
            "label": "",
            "kind": "bool",
            "idempotency_token": _tok(),
            "submit": "Add item",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_item_create_service_error(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    # choice without options → service raises ValueError
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items",
        data={
            "csrf_token": "x",
            "key": "c",
            "label": "C",
            "kind": "choice",
            "choice_options": "",
            "is_required": "y",
            "idempotency_token": _tok(),
            "submit": "Add item",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_item_create_idempotent(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "key": "k",
        "label": "L",
        "kind": "bool",
        "is_required": "y",
        "choice_options": "",
        "idempotency_token": tok,
        "submit": "Add item",
    }
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/items", data=payload)
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/items", data=payload)
    count = db_session.query(ChecklistTemplateItem).filter_by(template_id=tpl.id).count()
    assert count == 1


@pytest.mark.e2e
def test_template_item_create_unknown_template(
    client_logged_in: FlaskClient,
) -> None:
    resp = client_logged_in.post(
        "/knowledge/templates/zz/items",
        data={
            "csrf_token": "x",
            "key": "k",
            "label": "L",
            "kind": "bool",
            "idempotency_token": _tok(),
            "submit": "Add item",
        },
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_item_delete_unknown(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.post(
        "/knowledge/templates/zz/items/yy/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_item_delete_wrong_template(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    item = ChecklistTemplateItemFactory()
    other = ChecklistTemplateFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/templates/{other.id.hex()}/items/{item.id.hex()}/delete",
        data={"csrf_token": "x"},
        follow_redirects=False,
    )
    assert resp.status_code == 302
    # The wrong-template branch flashes + redirects to /knowledge/templates.
    assert "/knowledge/templates" in resp.headers["Location"]
    assert db_session.get(ChecklistTemplateItem, item.id) is not None


# ── Extra coverage: GET branches and validation re-renders ──────────────────


@pytest.mark.e2e
def test_tag_new_get(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/tags/new")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_new_get(client_logged_in: FlaskClient) -> None:
    resp = client_logged_in.get("/knowledge/procedures/new")
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_new_duplicate_via_idempotency_replay_after_first(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    payload = {
        "csrf_token": "x",
        "title": "OnceAndOnly",
        "summary": "",
        "body": "",
        "tags": [],
        "idempotency_token": _tok(),
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/procedures/new", data=payload)
    # Fresh idempotency token; service-level body cap (oversize) triggers
    # the ValueError flash branch.
    big = "x" * 70000
    resp = client_logged_in.post(
        "/knowledge/procedures/new",
        data={**payload, "title": "BigBody", "body": big, "idempotency_token": _tok()},
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_edit_idempotency_replay_redirects_to_detail(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    doc = ProcedureDocumentFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "title": "First",
        "summary": "",
        "body": "",
        "tags": [],
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/procedures/{doc.id.hex()}/edit", data=payload)
    # Second submission with same token → flash + redirect to detail.
    resp = client_logged_in.post(
        f"/knowledge/procedures/{doc.id.hex()}/edit",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/knowledge/procedures/" in resp.headers["Location"]


@pytest.mark.e2e
def test_procedure_new_idempotent_replay_redirect_to_list(
    client_logged_in: FlaskClient,
) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "title": "FirstP",
        "summary": "",
        "body": "",
        "tags": [],
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/procedures/new", data=payload)
    resp = client_logged_in.post("/knowledge/procedures/new", data=payload, follow_redirects=False)
    assert resp.status_code == 302
    assert "/knowledge/procedures" in resp.headers["Location"]


@pytest.mark.e2e
def test_tag_edit_idempotent_replay(client_logged_in: FlaskClient, db_session: Session) -> None:
    tag = ProcedureTagFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "Orig",
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/tags/{tag.id.hex()}/edit", data=payload)
    resp = client_logged_in.post(
        f"/knowledge/tags/{tag.id.hex()}/edit",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 302
    assert "/knowledge/tags" in resp.headers["Location"]


@pytest.mark.e2e
def test_template_new_idempotent_replay(
    client_logged_in: FlaskClient,
) -> None:
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "ReplayT",
        "description": "",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post("/knowledge/templates/new", data=payload)
    resp = client_logged_in.post("/knowledge/templates/new", data=payload, follow_redirects=False)
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_edit_idempotent_replay(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "name": "First",
        "description": "",
        "is_active": "y",
        "idempotency_token": tok,
        "submit": "Save",
    }
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/edit", data=payload)
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/edit",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_template_item_create_idempotent_replay_to_edit(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    tpl = ChecklistTemplateFactory()
    db_session.flush()
    tok = _tok()
    payload = {
        "csrf_token": "x",
        "key": "k",
        "label": "L",
        "kind": "bool",
        "is_required": "y",
        "choice_options": "",
        "idempotency_token": tok,
        "submit": "Add item",
    }
    client_logged_in.post(f"/knowledge/templates/{tpl.id.hex()}/items", data=payload)
    resp = client_logged_in.post(
        f"/knowledge/templates/{tpl.id.hex()}/items",
        data=payload,
        follow_redirects=False,
    )
    assert resp.status_code == 302


@pytest.mark.e2e
def test_procedure_new_with_unknown_tag(client_logged_in: FlaskClient) -> None:
    # Submitting a tag id that's not in the DB → service raises ValueError.
    resp = client_logged_in.post(
        "/knowledge/procedures/new",
        data={
            "csrf_token": "x",
            "title": "WithBadTag",
            "summary": "",
            "body": "",
            "tags": ["00" * 16],
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200


@pytest.mark.e2e
def test_procedure_edit_with_unknown_tag(
    client_logged_in: FlaskClient, db_session: Session
) -> None:
    doc = ProcedureDocumentFactory()
    db_session.flush()
    resp = client_logged_in.post(
        f"/knowledge/procedures/{doc.id.hex()}/edit",
        data={
            "csrf_token": "x",
            "title": "X",
            "summary": "",
            "body": "",
            "tags": ["00" * 16],
            "is_active": "y",
            "idempotency_token": _tok(),
            "submit": "Save",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
