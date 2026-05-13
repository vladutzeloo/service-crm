"""Routes for the knowledge blueprint.

Surfaces:

- ``/knowledge/procedures`` — list + search (Postgres ``tsvector`` /
  SQLite ``LIKE``), tag filter, per-document view.
- ``/knowledge/procedures/new`` + ``.../edit`` — author/edit Markdown.
- ``/knowledge/tags`` — admin CRUD for :class:`ProcedureTag`.
- ``/knowledge/templates`` — admin CRUD for :class:`ChecklistTemplate`
  and its items.
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from ..extensions import db
from ..shared import idempotency
from . import bp, forms, services
from ._translations import kind_label
from .markdown import render as render_markdown


def _tok() -> str:
    return uuid.uuid4().hex


def _hex_or_none(value: str | None) -> bytes | None:
    if not value:  # pragma: no cover - callers pre-filter falsy values
        return None
    return bytes.fromhex(value)


def _safe_hex(value: str | None) -> bytes | None:
    if not value:  # pragma: no cover - request.args.getlist drops empty strings
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:
        return None


def _actor_id() -> bytes:
    user = current_user
    return bytes(user.id)


def _record_idempotency(token: str, route: str) -> bool:
    if not token:  # pragma: no cover - every state-changing form ships a token
        return True
    return idempotency.record(db.session, user_id=_actor_id(), token=token, route=route)


def _split_choices(raw: str) -> list[str]:
    return [s.strip() for s in raw.split(",") if s.strip()]


# ── Procedures ──────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> Any:
    return redirect(url_for("knowledge.procedures_list"))


@bp.route("/procedures")
@login_required  # type: ignore[untyped-decorator]
def procedures_list() -> Any:
    q = request.args.get("q", "").strip()
    tag_args = request.args.getlist("tag")
    tag_ids: list[bytes] = [b for b in (_safe_hex(t) for t in tag_args) if b is not None]
    show = request.args.get("show", "active")
    active_only = show != "all"
    items = services.list_procedures(
        db.session, q=q, tag_ids=tag_ids or None, active_only=active_only
    )
    tags = services.list_tags(db.session, active_only=False)
    return render_template(
        "knowledge/procedures_list.html",
        items=items,
        tags=tags,
        q=q,
        active_tag_ids={t.hex() for t in tag_ids},
        show=show,
        tok=_tok(),
    )


@bp.route("/procedures/<procedure_hex>")
@login_required  # type: ignore[untyped-decorator]
def procedure_detail(procedure_hex: str) -> Any:
    try:
        doc = services.require_procedure(db.session, procedure_hex)
    except ValueError:
        flash(_("Procedure not found."), "error")
        return redirect(url_for("knowledge.procedures_list"))
    return render_template(
        "knowledge/procedure_detail.html",
        doc=doc,
        rendered=render_markdown(doc.body),
        tok=_tok(),
    )


@bp.route("/procedures/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def procedure_new() -> Any:
    form = forms.ProcedureCreateForm()
    tags = services.list_tags(db.session, active_only=False)
    form.tags.choices = [(t.id.hex(), t.name) for t in tags]
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.procedure_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.procedures_list"))
        try:
            tag_ids = [_hex_or_none(v) for v in (form.tags.data or [])]
            tag_bytes: list[bytes] = [b for b in tag_ids if b is not None]
            doc = services.create_procedure(
                db.session,
                title=form.title.data or "",
                summary=form.summary.data or "",
                body=form.body.data or "",
                tag_ids=tag_bytes,
            )
            db.session.commit()
            flash(_("Procedure created."), "success")
            return redirect(url_for("knowledge.procedure_detail", procedure_hex=doc.id.hex()))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "knowledge/procedure_edit.html",
        form=form,
        doc=None,
        tok=_tok(),
    )


@bp.route("/procedures/<procedure_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def procedure_edit(procedure_hex: str) -> Any:
    try:
        doc = services.require_procedure(db.session, procedure_hex)
    except ValueError:
        flash(_("Procedure not found."), "error")
        return redirect(url_for("knowledge.procedures_list"))
    form = forms.ProcedureEditForm()
    tags = services.list_tags(db.session, active_only=False)
    form.tags.choices = [(t.id.hex(), t.name) for t in tags]
    if request.method == "GET":
        form.title.data = doc.title
        form.summary.data = doc.summary
        form.body.data = doc.body
        form.tags.data = [t.id.hex() for t in doc.tags]
        form.is_active.data = doc.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.procedure_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.procedure_detail", procedure_hex=procedure_hex))
        try:
            tag_ids = [_hex_or_none(v) for v in (form.tags.data or [])]
            tag_bytes: list[bytes] = [b for b in tag_ids if b is not None]
            services.update_procedure(
                db.session,
                doc,
                title=form.title.data or "",
                summary=form.summary.data or "",
                body=form.body.data or "",
                tag_ids=tag_bytes,
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Procedure updated."), "success")
            return redirect(url_for("knowledge.procedure_detail", procedure_hex=procedure_hex))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "knowledge/procedure_edit.html",
        form=form,
        doc=doc,
        tok=_tok(),
    )


# ── Tags ────────────────────────────────────────────────────────────────────


@bp.route("/tags")
@login_required  # type: ignore[untyped-decorator]
def tags_list() -> Any:
    items = services.list_tags(db.session, active_only=False)
    return render_template("knowledge/tags_list.html", items=items, tok=_tok())


@bp.route("/tags/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def tag_new() -> Any:
    form = forms.TagCreateForm()
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.tag_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.tags_list"))
        try:
            services.create_tag(db.session, code=form.code.data or "", name=form.name.data or "")
            db.session.commit()
            flash(_("Tag created."), "success")
            return redirect(url_for("knowledge.tags_list"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "knowledge/tag_edit.html",
        form=form,
        tag=None,
        tok=_tok(),
    )


@bp.route("/tags/<tag_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def tag_edit(tag_hex: str) -> Any:
    try:
        tag = services.require_tag(db.session, tag_hex)
    except ValueError:
        flash(_("Tag not found."), "error")
        return redirect(url_for("knowledge.tags_list"))
    form = forms.TagEditForm()
    if request.method == "GET":
        form.name.data = tag.name
        form.is_active.data = tag.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.tag_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.tags_list"))
        try:
            services.update_tag(
                db.session,
                tag,
                name=form.name.data or "",
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Tag updated."), "success")
            return redirect(url_for("knowledge.tags_list"))
        except ValueError as exc:  # pragma: no cover - form DataRequired catches empty
            flash(str(exc), "error")
    return render_template(
        "knowledge/tag_edit.html",
        form=form,
        tag=tag,
        tok=_tok(),
    )


# ── Checklist templates ─────────────────────────────────────────────────────


@bp.route("/templates")
@login_required  # type: ignore[untyped-decorator]
def templates_list() -> Any:
    items = services.list_templates(db.session, active_only=False)
    return render_template(
        "knowledge/templates_list.html",
        items=items,
        tok=_tok(),
    )


@bp.route("/templates/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def template_new() -> Any:
    form = forms.TemplateCreateForm()
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.template_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.templates_list"))
        try:
            tpl = services.create_template(
                db.session,
                name=form.name.data or "",
                description=form.description.data or "",
            )
            db.session.commit()
            flash(_("Template created."), "success")
            return redirect(url_for("knowledge.template_edit", template_hex=tpl.id.hex()))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "knowledge/template_edit.html",
        form=form,
        template=None,
        item_form=forms.TemplateItemForm(),
        tok=_tok(),
        kind_label=kind_label,
    )


@bp.route("/templates/<template_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def template_edit(template_hex: str) -> Any:
    try:
        template = services.require_template(db.session, template_hex)
    except ValueError:
        flash(_("Template not found."), "error")
        return redirect(url_for("knowledge.templates_list"))
    form = forms.TemplateEditForm()
    if request.method == "GET":
        form.name.data = template.name
        form.description.data = template.description
        form.is_active.data = template.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "knowledge.template_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("knowledge.templates_list"))
        try:
            services.update_template(
                db.session,
                template,
                name=form.name.data or "",
                description=form.description.data or "",
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Template updated."), "success")
            return redirect(url_for("knowledge.templates_list"))
        except ValueError as exc:  # pragma: no cover - form DataRequired catches empty
            flash(str(exc), "error")
    return render_template(
        "knowledge/template_edit.html",
        form=form,
        template=template,
        item_form=forms.TemplateItemForm(),
        tok=_tok(),
        kind_label=kind_label,
    )


@bp.route("/templates/<template_hex>/items", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def template_item_create(template_hex: str) -> Any:
    try:
        template = services.require_template(db.session, template_hex)
    except ValueError:
        flash(_("Template not found."), "error")
        return redirect(url_for("knowledge.templates_list"))
    form = forms.TemplateItemForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(url_for("knowledge.template_edit", template_hex=template_hex))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "knowledge.template_item_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("knowledge.template_edit", template_hex=template_hex))
    try:
        services.add_template_item(
            db.session,
            template_id=template.id,
            key=form.key.data or "",
            label=form.label.data or "",
            kind=form.kind.data or "bool",
            is_required=bool(form.is_required.data),
            choice_options=_split_choices(form.choice_options.data or "") or None,
        )
        db.session.commit()
        flash(_("Item added."), "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("knowledge.template_edit", template_hex=template_hex))


@bp.route(
    "/templates/<template_hex>/items/<item_hex>/delete",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def template_item_delete(template_hex: str, item_hex: str) -> Any:
    try:
        template = services.require_template(db.session, template_hex)
        item = services.require_template_item(db.session, item_hex)
    except ValueError:
        flash(_("Item not found."), "error")
        return redirect(url_for("knowledge.templates_list"))
    if item.template_id != template.id:
        flash(_("Item not found."), "error")
        return redirect(url_for("knowledge.templates_list"))
    services.delete_template_item(db.session, item)
    db.session.commit()
    flash(_("Item removed."), "success")
    return redirect(url_for("knowledge.template_edit", template_hex=template_hex))


__all__: list[str] = []
