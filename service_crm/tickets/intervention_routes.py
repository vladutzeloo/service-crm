"""Intervention / parts routes for the tickets blueprint.

Mounted under ``/tickets``. Each intervention is always reached via its
parent ticket: ``/tickets/<ticket_hex>/interventions/...``. The
``parts`` lookup admin lives under ``/tickets/parts/...``.

Routes are intentionally thin: parse the request, call into
:mod:`.intervention_services`, render or redirect. RBAC is checked by
``@login_required``; per-action role guards are out of scope for v0.6
(parity with the rest of the blueprint).
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import abort, flash, redirect, render_template, request, send_file, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from ..auth.models import User
from ..extensions import db
from ..shared import idempotency
from ..shared.uploads import UploadRejected
from . import bp, intervention_forms, intervention_services, services
from ._intervention_translations import finding_kind_label
from ._translations import priority_label, status_label, status_tone, type_label


def _tok() -> str:
    return uuid.uuid4().hex


def _hex_or_none(value: str | None) -> bytes | None:
    if not value:
        return None
    return bytes.fromhex(value)


def _actor_id() -> bytes:
    user = current_user
    if not user or not user.is_authenticated:  # pragma: no cover - guarded by @login_required
        abort(401)
    return bytes(user.id)


def _record_idempotency(token: str, route: str) -> bool:
    if not token:  # pragma: no cover - every state-changing form ships a token
        return True
    return idempotency.record(db.session, user_id=_actor_id(), token=token, route=route)


def _populate_intervention_choices(
    form: intervention_forms.InterventionCreateForm | intervention_forms.InterventionEditForm,
) -> None:
    techs = db.session.query(User).filter(User.is_active.is_(True)).order_by(User.email).all()
    choices: list[tuple[str, str]] = [("", _("— unassigned —"))]
    choices.extend((u.id.hex(), u.email) for u in techs)
    form.technician_user_id.choices = choices


def _populate_part_usage_choices(form: intervention_forms.InterventionPartUsageForm) -> None:
    parts = intervention_services.list_parts(db.session)
    choices: list[tuple[str, str]] = [("", _("— ad-hoc —"))]
    choices.extend((p.id.hex(), p.label) for p in parts)
    form.part_id.choices = choices


# ── Intervention: create / edit / stop / delete ─────────────────────────────


@bp.route("/<ticket_hex>/interventions/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def intervention_new(ticket_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
    except ValueError:
        flash(_("Ticket not found."), "error")
        return redirect(url_for("tickets.list_tickets"))

    form = intervention_forms.InterventionCreateForm()
    _populate_intervention_choices(form)
    if request.method == "GET":
        # Pre-fill the technician with the current user (mobile flow).
        form.technician_user_id.data = _actor_id().hex()
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.intervention_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("tickets.detail", ticket_hex=ticket_hex))
        try:
            intervention = intervention_services.create_intervention(
                db.session,
                ticket_id=ticket.id,
                technician_user_id=_hex_or_none(form.technician_user_id.data),
                started_at=form.started_at.data,
                summary=form.summary.data or "",
            )
            db.session.commit()
            flash(_("Intervention started."), "success")
            return redirect(
                url_for(
                    "tickets.intervention_detail",
                    ticket_hex=ticket_hex,
                    intervention_hex=intervention.id.hex(),
                )
            )
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "tickets/intervention_edit.html",
        form=form,
        ticket=ticket,
        intervention=None,
        tok=_tok(),
    )


@bp.route("/<ticket_hex>/interventions/<intervention_hex>")
@login_required  # type: ignore[untyped-decorator]
def intervention_detail(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)

    action_form = intervention_forms.InterventionActionForm()
    finding_form = intervention_forms.InterventionFindingForm()
    part_form = intervention_forms.InterventionPartUsageForm()
    _populate_part_usage_choices(part_form)
    photo_form = intervention_forms.InterventionPhotoForm()
    stop_form = intervention_forms.InterventionStopForm()

    photos = intervention_services.list_intervention_photos(db.session, intervention.id)
    grouped_parts = intervention_services.coalesce_parts(intervention.parts)

    return render_template(
        "tickets/intervention_detail.html",
        ticket=ticket,
        intervention=intervention,
        action_form=action_form,
        finding_form=finding_form,
        part_form=part_form,
        photo_form=photo_form,
        stop_form=stop_form,
        photos=photos,
        grouped_parts=grouped_parts,
        finding_kind_label=finding_kind_label,
        status_label=status_label,
        status_tone=status_tone,
        priority_label=priority_label,
        type_label=type_label,
        tok=_tok(),
    )


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/edit",
    methods=["GET", "POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_edit(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)

    form = intervention_forms.InterventionEditForm()
    _populate_intervention_choices(form)
    if request.method == "GET":
        form.technician_user_id.data = (
            intervention.technician_user_id.hex() if intervention.technician_user_id else ""
        )
        form.started_at.data = intervention.started_at
        form.ended_at.data = intervention.ended_at
        form.summary.data = intervention.summary
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.intervention_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(
                url_for(
                    "tickets.intervention_detail",
                    ticket_hex=ticket_hex,
                    intervention_hex=intervention_hex,
                )
            )
        try:
            intervention_services.update_intervention(
                db.session,
                intervention,
                technician_user_id=_hex_or_none(form.technician_user_id.data),
                started_at=form.started_at.data,
                ended_at=form.ended_at.data,
                summary=form.summary.data or "",
            )
            db.session.commit()
            flash(_("Intervention updated."), "success")
            return redirect(
                url_for(
                    "tickets.intervention_detail",
                    ticket_hex=ticket_hex,
                    intervention_hex=intervention_hex,
                )
            )
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "tickets/intervention_edit.html",
        form=form,
        ticket=ticket,
        intervention=intervention,
        tok=_tok(),
    )


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/stop",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_stop(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)
    form = intervention_forms.InterventionStopForm()
    if not form.validate_on_submit():  # pragma: no cover - form has no validators
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.intervention_stop"):
        flash(_("This request was already submitted."), "info")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    try:
        intervention_services.stop_intervention(db.session, intervention)
        db.session.commit()
        flash(_("Intervention stopped."), "success")
    except ValueError as exc:  # pragma: no cover - guard already validated
        flash(str(exc), "error")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


# ── Actions ─────────────────────────────────────────────────────────────────


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/actions",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_action_create(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)
    form = intervention_forms.InterventionActionForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.intervention_action_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    try:
        intervention_services.add_action(
            db.session,
            intervention_id=intervention.id,
            description=form.description.data or "",
            duration_minutes=form.duration_minutes.data,
        )
        db.session.commit()
        flash(_("Action added."), "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/actions/<action_hex>/delete",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_action_delete(ticket_hex: str, intervention_hex: str, action_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
        action = intervention_services.require_action(db.session, action_hex)
    except ValueError:
        flash(_("Action not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id or action.intervention_id != intervention.id:
        abort(404)
    intervention_services.delete_action(db.session, action)
    db.session.commit()
    flash(_("Action removed."), "success")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


# ── Findings ────────────────────────────────────────────────────────────────


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/findings",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_finding_create(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)
    form = intervention_forms.InterventionFindingForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.intervention_finding_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    try:
        intervention_services.add_finding(
            db.session,
            intervention_id=intervention.id,
            description=form.description.data or "",
            is_root_cause=bool(form.is_root_cause.data),
        )
        db.session.commit()
        flash(_("Finding recorded."), "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/findings/<finding_hex>/delete",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_finding_delete(ticket_hex: str, intervention_hex: str, finding_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
        finding = intervention_services.require_finding(db.session, finding_hex)
    except ValueError:
        flash(_("Finding not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id or finding.intervention_id != intervention.id:
        abort(404)
    intervention_services.delete_finding(db.session, finding)
    db.session.commit()
    flash(_("Finding removed."), "success")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


# ── Part usage ──────────────────────────────────────────────────────────────


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/parts",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_part_create(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)
    form = intervention_forms.InterventionPartUsageForm()
    _populate_part_usage_choices(form)
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.intervention_part_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    try:
        intervention_services.add_part_usage(
            db.session,
            intervention_id=intervention.id,
            part_id=_hex_or_none(form.part_id.data),
            part_code=form.part_code.data or "",
            description=form.description.data or "",
            quantity=int(form.quantity.data or 1),
            unit=form.unit.data or "pcs",
        )
        db.session.commit()
        flash(_("Part recorded."), "success")
    except ValueError as exc:
        flash(str(exc), "error")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/parts/<usage_hex>/delete",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_part_delete(ticket_hex: str, intervention_hex: str, usage_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
        usage = intervention_services.require_part_usage(db.session, usage_hex)
    except ValueError:
        flash(_("Part usage not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id or usage.intervention_id != intervention.id:
        abort(404)
    intervention_services.delete_part_usage(db.session, usage)
    db.session.commit()
    flash(_("Part usage removed."), "success")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


# ── Photo uploads ───────────────────────────────────────────────────────────


@bp.route(
    "/<ticket_hex>/interventions/<intervention_hex>/photos",
    methods=["POST"],
)
@login_required  # type: ignore[untyped-decorator]
def intervention_photo_create(ticket_hex: str, intervention_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
    except ValueError:
        flash(_("Intervention not found."), "error")
        return redirect(url_for("tickets.list_tickets"))
    if intervention.ticket_id != ticket.id:
        abort(404)
    form = intervention_forms.InterventionPhotoForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "tickets.intervention_photo_create"):
        flash(_("This request was already submitted."), "info")
        return redirect(
            url_for(
                "tickets.intervention_detail",
                ticket_hex=ticket_hex,
                intervention_hex=intervention_hex,
            )
        )
    upload = form.upload.data
    try:
        intervention_services.add_intervention_photo(
            db.session,
            intervention=intervention,
            uploader_user_id=_actor_id(),
            stream=upload.stream,
            filename=upload.filename or "upload",
            declared_content_type=upload.mimetype or "",
        )
        db.session.commit()
        flash(_("Photo uploaded."), "success")
    except UploadRejected as exc:
        flash(str(exc), "error")
    return redirect(
        url_for(
            "tickets.intervention_detail",
            ticket_hex=ticket_hex,
            intervention_hex=intervention_hex,
        )
    )


@bp.route("/<ticket_hex>/interventions/<intervention_hex>/photos/<photo_hex>")
@login_required  # type: ignore[untyped-decorator]
def intervention_photo_download(ticket_hex: str, intervention_hex: str, photo_hex: str) -> Any:
    try:
        ticket = services.require_ticket(db.session, ticket_hex)
        intervention = intervention_services.require_intervention(db.session, intervention_hex)
        attachment = services.require_attachment(db.session, photo_hex, ticket)
    except ValueError:
        abort(404)
    if attachment.intervention_id != intervention.id:
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


# ── Parts lookup admin ──────────────────────────────────────────────────────


@bp.route("/parts")
@login_required  # type: ignore[untyped-decorator]
def parts_list() -> Any:
    q = request.args.get("q", "").strip()
    show = request.args.get("show", "active")
    active_only = show != "all"
    items = intervention_services.list_parts(db.session, q=q, active_only=active_only)
    return render_template(
        "tickets/parts_list.html",
        items=items,
        q=q,
        show=show,
        tok=_tok(),
    )


@bp.route("/parts/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def part_new() -> Any:
    form = intervention_forms.PartCreateForm()
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.part_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("tickets.parts_list"))
        try:
            intervention_services.create_part(
                db.session,
                code=form.code.data or "",
                description=form.description.data or "",
                unit=form.unit.data or "pcs",
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Part created."), "success")
            return redirect(url_for("tickets.parts_list"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "tickets/part_edit.html",
        form=form,
        part=None,
        tok=_tok(),
    )


@bp.route("/parts/<part_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def part_edit(part_hex: str) -> Any:
    try:
        part = intervention_services.require_part(db.session, part_hex)
    except ValueError:
        flash(_("Part not found."), "error")
        return redirect(url_for("tickets.parts_list"))
    form = intervention_forms.PartEditForm()
    if request.method == "GET":
        form.description.data = part.description
        form.unit.data = part.unit
        form.notes.data = part.notes
        form.is_active.data = part.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "tickets.part_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("tickets.parts_list"))
        intervention_services.update_part(
            db.session,
            part,
            description=form.description.data or "",
            unit=form.unit.data or "pcs",
            notes=form.notes.data or "",
            is_active=bool(form.is_active.data),
        )
        db.session.commit()
        flash(_("Part updated."), "success")
        return redirect(url_for("tickets.parts_list"))
    return render_template(
        "tickets/part_edit.html",
        form=form,
        part=part,
        tok=_tok(),
    )


__all__: list[str] = []
