"""Tickets blueprint routes.

Thin views: parse the request, call ``services.py``, render or redirect.
The select-field choice population happens here so the forms stay pure
(no DB session at import time).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import (
    abort,
    flash,
    redirect,
    render_template,
    request,
    send_file,
    url_for,
)
from flask_babel import gettext as _
from flask_login import current_user, login_required

from ..auth.models import User
from ..clients.models import Client
from ..equipment.models import Equipment
from ..extensions import db
from ..shared import idempotency
from ..shared.uploads import UploadRejected
from . import bp, forms, services
from ._translations import (
    STATUS_LABELS,
    priority_label,
    priority_tone,
    status_label,
    status_tone,
    type_label,
)
from .state import IllegalTransition, TicketStatus, legal_transitions


def _tok() -> str:
    return uuid.uuid4().hex


def _hex_or_none(value: str | None) -> bytes | None:
    if not value:
        return None
    return bytes.fromhex(value)


def _safe_query_hex(value: str | None) -> bytes | None:
    try:
        return _hex_or_none(value)
    except ValueError:
        return None


def _actor_role() -> str:
    """Best-effort fetch of the current user's role name.

    All callers are inside ``@login_required`` routes, so the
    unauthenticated branches are unreachable from production paths.
    """
    user = current_user
    if not user or not user.is_authenticated:  # pragma: no cover - guarded by @login_required
        return "guest"
    role = getattr(user, "role", None)
    if role is None:  # pragma: no cover - users without role can't authenticate
        return "guest"
    return str(getattr(role, "name", "guest"))


def _actor_id() -> bytes:
    user = current_user
    if not user or not user.is_authenticated:  # pragma: no cover - guarded by @login_required
        abort(401)
    return bytes(user.id)


def _record_idempotency(token: str, route: str) -> bool:
    if not token:
        return True
    return idempotency.record(db.session, user_id=_actor_id(), token=token, route=route)


# ── Form choice population ───────────────────────────────────────────────────


def _populate_create_choices(
    form: forms.TicketCreateForm, *, selected_client_id: bytes | None
) -> None:
    clients = (
        db.session.query(Client).filter(Client.is_active.is_(True)).order_by(Client.name).all()
    )
    form.client_id.choices = [(c.id.hex(), c.name) for c in clients]

    equipment_choices: list[tuple[str, str]] = [("", _("— none —"))]
    if selected_client_id is not None:
        eqs = (
            db.session.query(Equipment)
            .filter(
                Equipment.client_id == selected_client_id,
                Equipment.is_active.is_(True),
            )
            .order_by(Equipment.asset_tag)
            .all()
        )
        equipment_choices.extend((eq.id.hex(), eq.label) for eq in eqs)
    form.equipment_id.choices = equipment_choices

    type_choices: list[tuple[str, str]] = [("", _("— none —"))]
    type_choices.extend(
        (t.id.hex(), type_label(t.code))
        for t in services.list_ticket_types(db.session)
    )
    form.type_id.choices = type_choices

    prio_choices: list[tuple[str, str]] = [("", _("— none —"))]
    prio_choices.extend(
        (p.id.hex(), priority_label(p.code))
        for p in services.list_ticket_priorities(db.session)
    )
    form.priority_id.choices = prio_choices

    assignee_choices: list[tuple[str, str]] = [("", _("— unassigned —"))]
    assignees = (
        db.session.query(User).filter(User.is_active.is_(True)).order_by(User.email).all()
    )
    assignee_choices.extend((u.id.hex(), u.email) for u in assignees)
    form.assignee_user_id.choices = assignee_choices


def _populate_transition_choices(
    form: forms.TicketTransitionForm, *, current: TicketStatus, role: str
) -> None:
    options = sorted(s.value for s in legal_transitions(current, role))
    form.to_state.choices = [(value, status_label(value)) for value in options]


# ── List ────────────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def list_tickets() -> Any:
    q = request.args.get("q", "").strip()
    statuses = request.args.getlist("status")
    statuses = [s for s in statuses if s in STATUS_LABELS]
    type_id = _safe_query_hex(request.args.get("type_id"))
    priority_id = _safe_query_hex(request.args.get("priority_id"))
    client_id = _safe_query_hex(request.args.get("client"))
    equipment_id = _safe_query_hex(request.args.get("equipment"))
    assigned = request.args.get("assigned_to")
    assignee_id: bytes | None = None
    if assigned == "me":
        assignee_id = _actor_id()
    elif assigned:
        assignee_id = _safe_query_hex(assigned)
    show = request.args.get("show", "open")
    open_only = show == "open" and not statuses
    page = max(1, int(request.args.get("page", 1)))

    items, total = services.list_tickets(
        db.session,
        q=q,
        statuses=statuses if statuses else None,
        type_id=type_id,
        priority_id=priority_id,
        client_id=client_id,
        equipment_id=equipment_id,
        assignee_user_id=assignee_id,
        open_only=open_only,
        page=page,
    )
    counts = services.status_counts(db.session)
    client = db.session.get(Client, client_id) if client_id is not None else None

    return render_template(
        "tickets/list.html",
        items=items,
        total=total,
        q=q,
        statuses=statuses,
        show=show,
        page=page,
        counts=counts,
        client=client,
        assigned=assigned,
        status_labels=STATUS_LABELS,
        status_label=status_label,
        status_tone=status_tone,
        priority_label=priority_label,
        priority_tone=priority_tone,
        type_label=type_label,
        types=services.list_ticket_types(db.session),
        priorities=services.list_ticket_priorities(db.session),
        active_type_id=request.args.get("type_id", ""),
        active_priority_id=request.args.get("priority_id", ""),
    )


# ── Create ──────────────────────────────────────────────────────────────────


@bp.route("/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def new_ticket() -> Any:
    pre_client_id = _safe_query_hex(request.args.get("client"))
    pre_equipment_id = _safe_query_hex(request.args.get("equipment"))
    if pre_equipment_id is not None and pre_client_id is None:
        eq = db.session.get(Equipment, pre_equipment_id)
        if eq is not None:
            pre_client_id = eq.client_id

    form = forms.TicketCreateForm()
    selected_client_hex = request.form.get("client_id") or (
        pre_client_id.hex() if pre_client_id else ""
    )
    selected_client_id = _safe_query_hex(selected_client_hex)
    _populate_create_choices(form, selected_client_id=selected_client_id)

    if request.method == "GET":
        if pre_client_id is not None:
            form.client_id.data = pre_client_id.hex()
        if pre_equipment_id is not None:
            form.equipment_id.data = pre_equipment_id.hex()
        default_type = services.default_ticket_type(db.session)
        if default_type is not None:
            form.type_id.data = default_type.id.hex()
        default_prio = services.default_ticket_priority(db.session)
        if default_prio is not None:
            form.priority_id.data = default_prio.id.hex()

    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.new_ticket"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("tickets.list_tickets"))
        try:
            ticket = services.create_ticket(
                db.session,
                client_id=bytes.fromhex(form.client_id.data or ""),
                equipment_id=_hex_or_none(form.equipment_id.data),
                type_id=_hex_or_none(form.type_id.data),
                priority_id=_hex_or_none(form.priority_id.data),
                assignee_user_id=_hex_or_none(form.assignee_user_id.data),
                title=form.title.data or "",
                description=form.description.data or "",
                due_at=form.due_at.data,
                sla_due_at=form.sla_due_at.data,
            )
            db.session.commit()
            flash(_("Ticket %(label)s created.", label=ticket.label), "success")
            return redirect(url_for("tickets.detail", ticket_hex=ticket.id.hex()))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "tickets/edit.html",
        form=form,
        ticket=None,
        tok=_tok(),
    )


# ── Detail ──────────────────────────────────────────────────────────────────


@bp.route("/<ticket_hex>")
@login_required  # type: ignore[untyped-decorator]
def detail(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    tab = request.args.get("tab", "history")
    transition_form = forms.TicketTransitionForm()
    role = _actor_role()
    _populate_transition_choices(transition_form, current=ticket.status_enum, role=role)
    comment_form = forms.TicketCommentForm()
    attachment_form = forms.TicketAttachmentForm()
    delete_attachment_form = forms.TicketAttachmentDeleteForm()

    history = services.list_history(db.session, ticket.id)
    comments = services.list_comments(db.session, ticket.id)
    attachments = services.list_attachments(db.session, ticket.id)
    legal = sorted(s.value for s in legal_transitions(ticket.status_enum, role))

    return render_template(
        "tickets/detail.html",
        ticket=ticket,
        tab=tab,
        transition_form=transition_form,
        comment_form=comment_form,
        attachment_form=attachment_form,
        delete_attachment_form=delete_attachment_form,
        history=history,
        comments=comments,
        attachments=attachments,
        legal_transitions=legal,
        status_label=status_label,
        status_tone=status_tone,
        priority_label=priority_label,
        priority_tone=priority_tone,
        type_label=type_label,
        tok=_tok(),
    )


# ── Edit ────────────────────────────────────────────────────────────────────


@bp.route("/<ticket_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def edit_ticket(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    form = forms.TicketEditForm()
    _populate_create_choices(form, selected_client_id=ticket.client_id)

    if request.method == "GET":
        form.client_id.data = ticket.client_id.hex()
        form.equipment_id.data = ticket.equipment_id.hex() if ticket.equipment_id else ""
        form.type_id.data = ticket.type_id.hex() if ticket.type_id else ""
        form.priority_id.data = ticket.priority_id.hex() if ticket.priority_id else ""
        form.assignee_user_id.data = (
            ticket.assignee_user_id.hex() if ticket.assignee_user_id else ""
        )
        form.title.data = ticket.title
        form.description.data = ticket.description
        form.due_at.data = ticket.due_at
        form.sla_due_at.data = ticket.sla_due_at

    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.edit_ticket"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))
        try:
            services.update_ticket(
                db.session,
                ticket,
                title=form.title.data or "",
                description=form.description.data or "",
                equipment_id=_hex_or_none(form.equipment_id.data),
                type_id=_hex_or_none(form.type_id.data),
                priority_id=_hex_or_none(form.priority_id.data),
                assignee_user_id=_hex_or_none(form.assignee_user_id.data),
                due_at=form.due_at.data,
                sla_due_at=form.sla_due_at.data,
            )
            db.session.commit()
            flash(_("Ticket updated."), "success")
            return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "tickets/edit.html",
        form=form,
        ticket=ticket,
        tok=_tok(),
    )


# ── Transition ──────────────────────────────────────────────────────────────


@bp.route("/<ticket_hex>/transition", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def transition(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    form = forms.TicketTransitionForm()
    role = _actor_role()
    _populate_transition_choices(form, current=ticket.status_enum, role=role)
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))

    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.transition"):
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))

    to_state_raw = form.to_state.data or ""
    try:
        to_state = TicketStatus(to_state_raw)
    except ValueError:
        flash(_("Unknown target status."), "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))

    try:
        services.transition_ticket(
            db.session,
            ticket,
            to_state=to_state,
            role=role,
            reason=form.reason.data or "",
            reason_code=form.reason_code.data or "",
        )
        db.session.commit()
        flash(_("Status updated."), "success")
    except IllegalTransition as exc:
        flash(str(exc), "error")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))


# ── Comments ────────────────────────────────────────────────────────────────


@bp.route("/<ticket_hex>/comments", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def comment_create(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    form = forms.TicketCommentForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="comments"))

    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.comment_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="comments"))

    try:
        services.add_comment(
            db.session,
            ticket_id=ticket.id,
            author_user_id=_actor_id(),
            body=form.body.data or "",
        )
        db.session.commit()
        flash(_("Comment added."), "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="comments"))


# ── Attachments ─────────────────────────────────────────────────────────────


@bp.route("/<ticket_hex>/attachments", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def attachment_create(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    form = forms.TicketAttachmentForm()
    if not form.validate_on_submit():
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))

    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.attachment_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))

    upload = form.upload.data
    try:
        services.add_attachment(
            db.session,
            ticket=ticket,
            uploader_user_id=_actor_id(),
            stream=upload.stream,
            filename=upload.filename or "upload",
            declared_content_type=upload.mimetype or "",
        )
        db.session.commit()
        flash(_("Attachment uploaded."), "success")
    except UploadRejected as exc:
        # ``UploadRejected`` subclasses ``ValueError``, so catching it
        # explicitly is enough for everything ``services.add_attachment``
        # currently raises.
        flash(str(exc), "error")
    return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))


@bp.route("/<ticket_hex>/attachments/<attachment_hex>")
@login_required  # type: ignore[untyped-decorator]
def attachment_download(ticket_hex: str, attachment_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        attachment = services.require_attachment(db.session, attachment_hex, ticket)
    except ValueError:
        abort(404)
    if not attachment.is_active:
        abort(404)
    from ..shared import uploads as _uploads

    try:
        path, _size = _uploads.open_stored(attachment.storage_key)
    except FileNotFoundError:
        abort(404)
    return send_file(
        path,
        mimetype=attachment.content_type or "application/octet-stream",
        download_name=attachment.filename,
        as_attachment=False,
    )


@bp.route("/<ticket_hex>/attachments/<attachment_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def attachment_delete(ticket_hex: str, attachment_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        attachment = services.require_attachment(db.session, attachment_hex, ticket)
    except ValueError:
        flash(_("Attachment not found."), "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))

    form = forms.TicketAttachmentDeleteForm()
    if not form.validate_on_submit():
        flash(_("A reason is required to delete an attachment."), "error")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))

    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.attachment_delete"):
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))

    try:
        services.soft_delete_attachment(db.session, attachment, reason=form.reason.data or "")
        db.session.commit()
        flash(_("Attachment removed."), "success")
    except ValueError as exc:  # pragma: no cover - form ``DataRequired`` makes this unreachable
        flash(str(exc), "error")
    return redirect(url_for("tickets.detail", ticket_hex=ticket_hex, tab="attachments"))


# ── Lookup admin (rename/deactivate; no add/delete) ─────────────────────────


@bp.route("/types")
@login_required  # type: ignore[untyped-decorator]
def list_types() -> Any:
    items = services.list_ticket_types(db.session, active_only=False)
    return render_template(
        "tickets/types_list.html",
        items=items,
        type_label=type_label,
        tok=_tok(),
    )


@bp.route("/types/<type_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def type_edit(type_hex: str) -> Any:
    try:
        obj = services.require_ticket_type(db.session, type_hex)
    except ValueError:
        flash(_("Ticket type not found."), "error")
        return redirect(url_for("tickets.list_types"))
    form = forms.TicketLookupEditForm()
    if request.method == "GET":
        form.label.data = obj.label
        form.is_active.data = "1" if obj.is_active else "0"
    if form.validate_on_submit():
        services.update_ticket_type(
            db.session,
            obj,
            label=form.label.data or "",
            is_active=(form.is_active.data == "1"),
        )
        db.session.commit()
        flash(_("Ticket type updated."), "success")
        return redirect(url_for("tickets.list_types"))
    return render_template(
        "tickets/lookup_edit.html",
        form=form,
        kind="type",
        obj=obj,
        title=_("Edit ticket type"),
        cancel_href=url_for("tickets.list_types"),
        tok=_tok(),
    )


@bp.route("/priorities")
@login_required  # type: ignore[untyped-decorator]
def list_priorities() -> Any:
    items = services.list_ticket_priorities(db.session, active_only=False)
    return render_template(
        "tickets/priorities_list.html",
        items=items,
        priority_label=priority_label,
        tok=_tok(),
    )


@bp.route("/priorities/<priority_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def priority_edit(priority_hex: str) -> Any:
    try:
        obj = services.require_ticket_priority(db.session, priority_hex)
    except ValueError:
        flash(_("Ticket priority not found."), "error")
        return redirect(url_for("tickets.list_priorities"))
    form = forms.TicketLookupEditForm()
    if request.method == "GET":
        form.label.data = obj.label
        form.is_active.data = "1" if obj.is_active else "0"
    if form.validate_on_submit():
        services.update_ticket_priority(
            db.session,
            obj,
            label=form.label.data or "",
            is_active=(form.is_active.data == "1"),
        )
        db.session.commit()
        flash(_("Ticket priority updated."), "success")
        return redirect(url_for("tickets.list_priorities"))
    return render_template(
        "tickets/lookup_edit.html",
        form=form,
        kind="priority",
        obj=obj,
        title=_("Edit ticket priority"),
        cancel_href=url_for("tickets.list_priorities"),
        tok=_tok(),
    )


__all__ = ["bp"]
