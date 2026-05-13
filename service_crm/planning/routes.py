"""Routes for the planning blueprint."""

from __future__ import annotations

import uuid
from datetime import date, timedelta
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from ..auth.models import User
from ..extensions import db
from ..shared import idempotency
from . import bp, forms, services
from .models import Technician


def _tok() -> str:
    return uuid.uuid4().hex


def _actor_id() -> bytes:
    user = current_user
    return bytes(user.id)


def _record_idempotency(token: str, route: str) -> bool:
    if not token:  # pragma: no cover - every state-changing form ships a token
        return True
    return idempotency.record(db.session, user_id=_actor_id(), token=token, route=route)


def _parse_date(raw: str | None) -> date | None:
    if not raw:
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        return None


# ── Technicians ─────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> Any:
    return redirect(url_for("planning.capacity"))


@bp.route("/technicians")
@login_required  # type: ignore[untyped-decorator]
def technicians_list() -> Any:
    show = request.args.get("show", "active")
    items = services.list_technicians(db.session, active_only=show != "all")
    return render_template(
        "planning/technicians_list.html",
        items=items,
        show=show,
        tok=_tok(),
    )


def _populate_user_choices(form: forms.TechnicianCreateForm) -> None:
    # Surface only users that don't already have a Technician row, so the
    # admin doesn't accidentally try to dual-add.
    bound_user_ids = {t.user_id for t in db.session.query(Technician).all()}
    candidates = db.session.query(User).filter(User.is_active.is_(True)).order_by(User.email).all()
    choices = [(u.id.hex(), u.email) for u in candidates if u.id not in bound_user_ids]
    form.user_id.choices = choices


@bp.route("/technicians/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def technician_new() -> Any:
    form = forms.TechnicianCreateForm()
    _populate_user_choices(form)
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(
            token, "planning.technician_new"
        ):  # pragma: no cover - retry path
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("planning.technicians_list"))
        try:
            tech = services.create_technician(
                db.session,
                user_id=bytes.fromhex(form.user_id.data or ""),
                display_name=form.display_name.data or "",
                timezone=form.timezone.data or "Europe/Bucharest",
                weekly_capacity_minutes=form.weekly_capacity_minutes.data
                or Technician.DEFAULT_WEEKLY_MINUTES,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Technician added."), "success")
            return redirect(url_for("planning.technician_detail", technician_hex=tech.id.hex()))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "planning/technician_edit.html",
        form=form,
        technician=None,
        tok=_tok(),
    )


@bp.route("/technicians/<technician_hex>")
@login_required  # type: ignore[untyped-decorator]
def technician_detail(technician_hex: str) -> Any:
    try:
        tech = services.require_technician(db.session, technician_hex)
    except ValueError:
        flash(_("Technician not found."), "error")
        return redirect(url_for("planning.technicians_list"))
    today = _today()
    slots = services.list_capacity_slots(
        db.session,
        technician_id=tech.id,
        start=today - timedelta(days=7),
        end=today + timedelta(days=14),
    )
    slot_form = forms.CapacitySlotForm()
    if (
        request.method == "GET" and not slot_form.day.data
    ):  # pragma: no branch - GET path pre-fills the date input
        slot_form.day.data = today
    return render_template(
        "planning/technician_detail.html",
        technician=tech,
        slots=slots,
        slot_form=slot_form,
        tok=_tok(),
    )


@bp.route("/technicians/<technician_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def technician_edit(technician_hex: str) -> Any:
    try:
        tech = services.require_technician(db.session, technician_hex)
    except ValueError:
        flash(_("Technician not found."), "error")
        return redirect(url_for("planning.technicians_list"))
    form = forms.TechnicianEditForm()
    if request.method == "GET":
        form.display_name.data = tech.display_name
        form.timezone.data = tech.timezone
        form.weekly_capacity_minutes.data = tech.weekly_capacity_minutes
        form.notes.data = tech.notes
        form.is_active.data = tech.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(
            token, "planning.technician_edit"
        ):  # pragma: no cover - retry path
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))
        try:
            services.update_technician(
                db.session,
                tech,
                display_name=form.display_name.data or "",
                timezone=form.timezone.data or tech.timezone,
                weekly_capacity_minutes=form.weekly_capacity_minutes.data
                or tech.weekly_capacity_minutes,
                notes=form.notes.data or "",
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Technician updated."), "success")
            return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))
        except ValueError as exc:  # pragma: no cover - service-level validation covered separately
            flash(str(exc), "error")
    return render_template(
        "planning/technician_edit.html",
        form=form,
        technician=tech,
        tok=_tok(),
    )


# ── Capacity ────────────────────────────────────────────────────────────────


def _today() -> date:
    from ..shared import clock

    return clock.now().date()


@bp.route("/capacity")
@login_required  # type: ignore[untyped-decorator]
def capacity() -> Any:
    today = _today()
    start = _parse_date(request.args.get("start")) or today
    end = _parse_date(request.args.get("end")) or (start + timedelta(days=13))
    if end < start:
        end = start + timedelta(days=13)
    load = services.daily_load(db.session, start=start, end=end)
    return render_template(
        "planning/capacity.html",
        load=load,
        start=start,
        end=end,
        days=[start + timedelta(days=i) for i in range((end - start).days + 1)],
        today=today,
        tok=_tok(),
    )


@bp.route("/technicians/<technician_hex>/slots", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def slot_upsert(technician_hex: str) -> Any:
    try:
        tech = services.require_technician(db.session, technician_hex)
    except ValueError:
        flash(_("Technician not found."), "error")
        return redirect(url_for("planning.technicians_list"))
    form = forms.CapacitySlotForm()
    if not form.validate_on_submit():
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "planning.slot_upsert"):  # pragma: no cover - retry path
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))
    try:
        services.upsert_capacity_slot(
            db.session,
            technician_id=tech.id,
            day=form.day.data,
            capacity_minutes=form.capacity_minutes.data or 0,
            notes=form.notes.data or "",
        )
        db.session.commit()
        flash(_("Capacity slot saved."), "success")
    except ValueError as exc:  # pragma: no cover - service-level validation covered separately
        flash(str(exc), "error")
    return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))


@bp.route("/technicians/<technician_hex>/slots/<slot_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def slot_delete(technician_hex: str, slot_hex: str) -> Any:
    try:
        tech = services.require_technician(db.session, technician_hex)
        slot = services.require_capacity_slot(db.session, slot_hex)
    except ValueError:
        flash(_("Capacity slot not found."), "error")
        return redirect(url_for("planning.technicians_list"))
    if slot.technician_id != tech.id:
        flash(_("Capacity slot not found."), "error")
        return redirect(url_for("planning.technicians_list"))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(token, "planning.slot_delete"):  # pragma: no cover - retry path
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))
    services.delete_capacity_slot(db.session, slot)
    db.session.commit()
    flash(_("Capacity slot removed."), "success")
    return redirect(url_for("planning.technician_detail", technician_hex=technician_hex))


__all__: list[str] = []
