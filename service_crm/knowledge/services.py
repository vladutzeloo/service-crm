"""Service layer for the knowledge blueprint.

Owns every query that hits ``checklist_*`` and ``procedure_*`` tables.
The frozen-snapshot rule for checklist runs lives in
:func:`start_checklist_run` — the template is copied into JSON at run
creation; nothing else writes ``snapshot`` or ``ChecklistRunItem`` rows
referencing a template that may later be edited.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import asc, func, or_
from sqlalchemy.orm import Session

from ..extensions import db
from ..shared import clock
from ..tickets.intervention_models import ServiceIntervention
from .models import (
    ChecklistRun,
    ChecklistRunItem,
    ChecklistTemplate,
    ChecklistTemplateItem,
    ProcedureDocument,
    ProcedureTag,
)


def _dialect() -> str:
    return db.engine.dialect.name


def _hex_to_bytes(hex_id: str, kind: str) -> bytes:
    try:
        return bytes.fromhex(hex_id)
    except ValueError as exc:
        raise ValueError(f"invalid {kind} id") from exc


# ── Checklist templates ─────────────────────────────────────────────────────


def list_templates(session: Session, *, active_only: bool = True) -> list[ChecklistTemplate]:
    q = session.query(ChecklistTemplate)
    if active_only:
        q = q.filter(ChecklistTemplate.is_active.is_(True))
    return q.order_by(asc(ChecklistTemplate.name)).all()


def require_template(session: Session, hex_id: str) -> ChecklistTemplate:
    tid = _hex_to_bytes(hex_id, "checklist template")
    obj = session.get(ChecklistTemplate, tid)
    if obj is None:
        raise ValueError("template not found")
    return obj


def create_template(session: Session, *, name: str, description: str = "") -> ChecklistTemplate:
    name = name.strip()
    if not name:
        raise ValueError("template name is required")
    existing = (
        session.query(ChecklistTemplate)
        .filter(func.lower(ChecklistTemplate.name) == name.lower())
        .first()
    )
    if existing is not None:
        raise ValueError("template name already exists")
    tpl = ChecklistTemplate(name=name, description=description.strip())
    session.add(tpl)
    session.flush()
    return tpl


def update_template(
    session: Session,
    template: ChecklistTemplate,
    *,
    name: str,
    description: str,
    is_active: bool,
) -> ChecklistTemplate:
    name = name.strip()
    if not name:
        raise ValueError("template name is required")
    template.name = name
    template.description = description.strip()
    template.is_active = is_active
    session.flush()
    return template


def add_template_item(
    session: Session,
    *,
    template_id: bytes,
    key: str,
    label: str,
    kind: str,
    is_required: bool = True,
    choice_options: list[str] | None = None,
    position: int | None = None,
) -> ChecklistTemplateItem:
    key = key.strip()
    label = label.strip()
    if not key:
        raise ValueError("item key is required")
    if not label:
        raise ValueError("item label is required")
    if kind not in ChecklistTemplateItem.KINDS:
        raise ValueError(f"unknown kind {kind!r}")
    if kind == "choice":
        if not choice_options:
            raise ValueError("choice items need at least one option")
    else:
        choice_options = None
    template = session.get(ChecklistTemplate, template_id)
    if template is None:
        raise ValueError("template not found")
    duplicate = (
        session.query(ChecklistTemplateItem)
        .filter(
            ChecklistTemplateItem.template_id == template_id,
            ChecklistTemplateItem.key == key,
        )
        .first()
    )
    if duplicate is not None:
        raise ValueError("item key already exists in this template")
    if position is None:
        existing_max = (
            session.query(func.coalesce(func.max(ChecklistTemplateItem.position), -1))
            .filter(ChecklistTemplateItem.template_id == template_id)
            .scalar()
        )
        position = int(existing_max if existing_max is not None else -1) + 1
    item = ChecklistTemplateItem(
        template_id=template_id,
        position=position,
        key=key,
        label=label,
        kind=kind,
        is_required=is_required,
        choice_options=choice_options,
    )
    session.add(item)
    session.flush()
    return item


def require_template_item(session: Session, hex_id: str) -> ChecklistTemplateItem:
    iid = _hex_to_bytes(hex_id, "template item")
    obj = session.get(ChecklistTemplateItem, iid)
    if obj is None:
        raise ValueError("item not found")
    return obj


def delete_template_item(session: Session, item: ChecklistTemplateItem) -> None:
    session.delete(item)
    session.flush()


# ── Checklist runs ──────────────────────────────────────────────────────────


def start_checklist_run(
    session: Session,
    *,
    template_id: bytes,
    intervention_id: bytes | None,
) -> ChecklistRun:
    """Snapshot the template into a new :class:`ChecklistRun`.

    After this call the source template can be edited or deleted; the
    run's ``snapshot`` JSON and its :class:`ChecklistRunItem` rows are
    independent.
    """
    template = session.get(ChecklistTemplate, template_id)
    if template is None:
        raise ValueError("template not found")
    if intervention_id is not None and session.get(ServiceIntervention, intervention_id) is None:
        raise ValueError("intervention not found")
    items_snapshot: list[dict[str, Any]] = []
    for item in template.items:
        items_snapshot.append(
            {
                "key": item.key,
                "label": item.label,
                "kind": item.kind,
                "is_required": item.is_required,
                "position": item.position,
                "choice_options": list(item.choice_options or []) or None,
                "template_item_id": item.id.hex(),
            }
        )
    snapshot: dict[str, Any] = {
        "template_id": template.id.hex(),
        "name": template.name,
        "description": template.description,
        "items": items_snapshot,
    }
    run = ChecklistRun(
        template_id=template.id,
        intervention_id=intervention_id,
        snapshot=snapshot,
    )
    session.add(run)
    session.flush()
    for item in template.items:
        session.add(
            ChecklistRunItem(
                run_id=run.id,
                template_item_id=item.id,
                position=item.position,
                key=item.key,
                label=item.label,
                kind=item.kind,
                is_required=item.is_required,
                answer=None,
            )
        )
    session.flush()
    return run


def require_run(session: Session, hex_id: str) -> ChecklistRun:
    rid = _hex_to_bytes(hex_id, "checklist run")
    obj = session.get(ChecklistRun, rid)
    if obj is None:
        raise ValueError("run not found")
    return obj


def answer_run_item(
    session: Session,
    item: ChecklistRunItem,
    *,
    answer: Any,
    notes: str = "",
) -> ChecklistRunItem:
    item.answer = _coerce_answer(item.kind, answer)
    item.notes = notes.strip()
    session.flush()
    return item


def _coerce_answer(kind: str, raw: Any) -> Any:  # noqa: PLR0911
    """Validate and normalise an answer to a checklist item.

    Returns ``None`` for "unanswered"; raises :class:`ValueError` on a
    type mismatch (e.g. ``"abc"`` on a ``number`` kind).
    """
    if raw is None or raw == "":
        return None
    if kind == "bool":
        if isinstance(raw, bool):
            return raw
        if isinstance(raw, str):
            return raw.lower() in {"y", "yes", "true", "1", "on"}
        return bool(raw)
    if kind == "number":
        try:
            return float(raw)
        except (TypeError, ValueError) as exc:
            raise ValueError("answer must be a number") from exc
    if kind == "text":
        return str(raw)
    if kind == "choice":
        return str(raw)
    raise ValueError(f"unknown item kind {kind!r}")  # pragma: no cover - guarded at write


def complete_run(
    session: Session,
    run: ChecklistRun,
    *,
    when: datetime | None = None,
) -> ChecklistRun:
    missing = [item for item in run.items if item.is_required and item.answer is None]
    if missing:
        raise ValueError("required items must be answered before completion")
    run.completed_at = when or clock.now()
    session.flush()
    return run


# ── Procedure tags ──────────────────────────────────────────────────────────


def list_tags(session: Session, *, active_only: bool = True) -> list[ProcedureTag]:
    q = session.query(ProcedureTag)
    if active_only:
        q = q.filter(ProcedureTag.is_active.is_(True))
    return q.order_by(asc(ProcedureTag.name)).all()


def require_tag(session: Session, hex_id: str) -> ProcedureTag:
    tid = _hex_to_bytes(hex_id, "procedure tag")
    obj = session.get(ProcedureTag, tid)
    if obj is None:
        raise ValueError("tag not found")
    return obj


def create_tag(session: Session, *, code: str, name: str) -> ProcedureTag:
    code = code.strip()
    name = name.strip()
    if not code:
        raise ValueError("tag code is required")
    if not name:
        raise ValueError("tag name is required")
    existing = (
        session.query(ProcedureTag).filter(func.lower(ProcedureTag.code) == code.lower()).first()
    )
    if existing is not None:
        raise ValueError("tag code already exists")
    tag = ProcedureTag(code=code, name=name)
    session.add(tag)
    session.flush()
    return tag


def update_tag(
    session: Session,
    tag: ProcedureTag,
    *,
    name: str,
    is_active: bool,
) -> ProcedureTag:
    name = name.strip()
    if not name:
        raise ValueError("tag name is required")
    tag.name = name
    tag.is_active = is_active
    session.flush()
    return tag


# ── Procedure documents ─────────────────────────────────────────────────────


def _procedure_search_filter(q: str) -> Any:
    q = q.strip()
    if not q:
        return None
    if _dialect() == "postgresql":
        import re

        from sqlalchemy import literal_column

        # Normalise hyphens / punctuation so ``plainto_tsquery`` doesn't
        # produce compound lexemes the indexed vector lacks. See
        # ``tickets.intervention_services._part_search_filter``.
        normalised = re.sub(r"[^\w\s]", " ", q)
        tsq = func.plainto_tsquery(literal_column("'simple'"), normalised)
        text = (
            func.coalesce(ProcedureDocument.title, "")
            + " "
            + func.coalesce(ProcedureDocument.summary, "")
            + " "
            + func.coalesce(ProcedureDocument.body, "")
        )
        return func.to_tsvector(literal_column("'simple'"), text).op("@@")(tsq)
    pattern = f"%{q.lower()}%"
    return or_(
        func.lower(ProcedureDocument.title).like(pattern),
        func.lower(ProcedureDocument.summary).like(pattern),
        func.lower(ProcedureDocument.body).like(pattern),
    )


def list_procedures(
    session: Session,
    *,
    q: str = "",
    tag_ids: list[bytes] | None = None,
    active_only: bool = True,
) -> list[ProcedureDocument]:
    base = session.query(ProcedureDocument)
    if active_only:
        base = base.filter(ProcedureDocument.is_active.is_(True))
    if tag_ids:
        base = base.filter(ProcedureDocument.tags.any(ProcedureTag.id.in_(tag_ids)))
    flt = _procedure_search_filter(q)
    if flt is not None:
        base = base.filter(flt)
    return base.order_by(asc(ProcedureDocument.title)).all()


def require_procedure(session: Session, hex_id: str) -> ProcedureDocument:
    pid = _hex_to_bytes(hex_id, "procedure")
    obj = session.get(ProcedureDocument, pid)
    if obj is None:
        raise ValueError("procedure not found")
    return obj


def create_procedure(
    session: Session,
    *,
    title: str,
    summary: str = "",
    body: str = "",
    tag_ids: list[bytes] | None = None,
) -> ProcedureDocument:
    title = title.strip()
    if not title:
        raise ValueError("title is required")
    if len(body.encode("utf-8")) > ProcedureDocument.BODY_MAX_BYTES:
        raise ValueError(f"body exceeds {ProcedureDocument.BODY_MAX_BYTES // 1024} KB")
    doc = ProcedureDocument(title=title, summary=summary.strip(), body=body)
    session.add(doc)
    session.flush()
    if tag_ids:
        _apply_tags(session, doc, tag_ids)
        session.flush()
    return doc


def update_procedure(
    session: Session,
    doc: ProcedureDocument,
    *,
    title: str,
    summary: str,
    body: str,
    tag_ids: list[bytes] | None,
    is_active: bool,
) -> ProcedureDocument:
    title = title.strip()
    if not title:
        raise ValueError("title is required")
    if len(body.encode("utf-8")) > ProcedureDocument.BODY_MAX_BYTES:
        raise ValueError(f"body exceeds {ProcedureDocument.BODY_MAX_BYTES // 1024} KB")
    doc.title = title
    doc.summary = summary.strip()
    doc.body = body
    doc.is_active = is_active
    _apply_tags(session, doc, tag_ids or [])
    session.flush()
    return doc


def _apply_tags(session: Session, doc: ProcedureDocument, tag_ids: list[bytes]) -> None:
    if not tag_ids:
        doc.tags = []
        return
    tags = session.query(ProcedureTag).filter(ProcedureTag.id.in_(tag_ids)).all()
    if len(tags) != len(set(tag_ids)):
        raise ValueError("unknown tag id")
    doc.tags = tags


__all__ = [
    "add_template_item",
    "answer_run_item",
    "complete_run",
    "create_procedure",
    "create_tag",
    "create_template",
    "delete_template_item",
    "list_procedures",
    "list_tags",
    "list_templates",
    "require_procedure",
    "require_run",
    "require_tag",
    "require_template",
    "require_template_item",
    "start_checklist_run",
    "update_procedure",
    "update_tag",
    "update_template",
]
