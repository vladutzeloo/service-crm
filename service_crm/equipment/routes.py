"""Equipment blueprint routes.

Thin views: parse the request, call ``services.py``, render or redirect.
The select-field choice population (clients, locations, models,
controllers) happens here so the forms stay pure.
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import login_required
from sqlalchemy.exc import IntegrityError

from ..clients.models import Client, Location
from ..extensions import db
from . import bp, forms, services
from .models import Equipment, EquipmentWarranty


def _tok() -> str:
    return uuid.uuid4().hex


def _hex_or_none(value: str | None) -> bytes | None:
    """Strict hex → bytes converter.

    Returns ``None`` only for genuinely empty input. Malformed hex raises
    ``ValueError`` so the calling route can flash it as a form error
    rather than silently dropping it. Use :func:`_safe_query_hex` for
    query-string parsing where an invalid id should fall back to "no
    filter" instead of bubbling up as an exception.
    """
    if not value:
        return None
    return bytes.fromhex(value)


def _safe_query_hex(value: str | None) -> bytes | None:
    """Permissive hex → bytes converter for URL query parameters.

    ``?client=garbage`` from a bookmark or stale link shouldn't 500;
    fall back to "no filter applied" instead.
    """
    try:
        return _hex_or_none(value)
    except ValueError:
        return None


# ── Form choice population ───────────────────────────────────────────────────


def _populate_equipment_choices(
    form: forms.EquipmentForm, *, selected_client_id: bytes | None
) -> None:
    clients = (
        db.session.query(Client).filter(Client.is_active.is_(True)).order_by(Client.name).all()
    )
    form.client_id.choices = [(c.id.hex(), c.name) for c in clients]

    location_choices: list[tuple[str, str]] = [("", _("— none —"))]
    if selected_client_id is not None:
        locs = (
            db.session.query(Location)
            .filter(Location.client_id == selected_client_id)
            .order_by(Location.label)
            .all()
        )
        location_choices.extend((loc.id.hex(), loc.label) for loc in locs)
    form.location_id.choices = location_choices

    model_choices: list[tuple[str, str]] = [("", _("— none —"))]
    model_choices.extend((m.id.hex(), m.label) for m in services.list_equipment_models(db.session))
    form.equipment_model_id.choices = model_choices

    ctrl_choices: list[tuple[str, str]] = [("", _("— none —"))]
    ctrl_choices.extend((c.id.hex(), c.name) for c in services.list_controller_types(db.session))
    form.controller_type_id.choices = ctrl_choices


def _populate_model_choices(form: forms.EquipmentModelForm) -> None:
    ctrl_choices: list[tuple[str, str]] = [("", _("— none —"))]
    ctrl_choices.extend((c.id.hex(), c.name) for c in services.list_controller_types(db.session))
    form.controller_type_id.choices = ctrl_choices


# ── Equipment list / detail / CRUD ───────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def list_equipment() -> Any:
    q = request.args.get("q", "").strip()
    show = request.args.get("show", "active")
    active_only = show != "all"
    page = max(1, int(request.args.get("page", 1)))
    client_id = _safe_query_hex(request.args.get("client"))

    items, total = services.list_equipment(
        db.session,
        q=q,
        client_id=client_id,
        active_only=active_only,
        page=page,
    )
    client = db.session.get(Client, client_id) if client_id is not None else None
    return render_template(
        "equipment/list.html",
        items=items,
        total=total,
        q=q,
        show=show,
        page=page,
        client=client,
    )


@bp.route("/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def new_equipment() -> Any:
    pre_client_id = _safe_query_hex(request.args.get("client"))
    form = forms.EquipmentForm()

    # Re-bind ``selected_client_id`` from posted data so the location
    # dropdown lists the right rows when validation fails.
    selected_client_hex = request.form.get("client_id") or (
        pre_client_id.hex() if pre_client_id else ""
    )
    # Best-effort here — we're only narrowing the location dropdown; the
    # authoritative validation happens via ``services.create_equipment``
    # (or ``update_equipment``) below.
    selected_client_id = _safe_query_hex(selected_client_hex)
    _populate_equipment_choices(form, selected_client_id=selected_client_id)

    if pre_client_id is not None and request.method == "GET":
        form.client_id.data = pre_client_id.hex()

    if form.validate_on_submit():
        try:
            eq = services.create_equipment(
                db.session,
                client_id=bytes.fromhex(form.client_id.data or ""),
                location_id=_hex_or_none(form.location_id.data),
                equipment_model_id=_hex_or_none(form.equipment_model_id.data),
                controller_type_id=_hex_or_none(form.controller_type_id.data),
                serial_number=form.serial_number.data or "",
                asset_tag=form.asset_tag.data or "",
                install_date=form.install_date.data,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Equipment created."), "success")
            return redirect(url_for("equipment.detail", equipment_hex=eq.id.hex()))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("equipment/edit.html", form=form, equipment=None, tok=_tok())


@bp.route("/<equipment_hex>")
@login_required  # type: ignore[untyped-decorator]
def detail(equipment_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))

    tab = request.args.get("tab", "warranties")
    edit_warranty = request.args.get("edit_warranty")
    warranty_form = forms.WarrantyForm(prefix="warranty")
    edit_warranty_obj: EquipmentWarranty | None = None
    if edit_warranty:
        try:
            edit_warranty_obj = services.require_warranty(db.session, edit_warranty, eq)
            warranty_form = forms.WarrantyForm(prefix="warranty", obj=edit_warranty_obj)
        except ValueError:
            edit_warranty = None

    return render_template(
        "equipment/detail.html",
        equipment=eq,
        tab=tab,
        warranty_form=warranty_form,
        edit_warranty=edit_warranty,
        edit_warranty_obj=edit_warranty_obj,
        tok=_tok(),
    )


@bp.route("/<equipment_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def edit_equipment(equipment_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))

    form = forms.EquipmentForm(obj=_form_data_for_equipment(eq))
    selected_client_hex = request.form.get("client_id") or eq.client_id.hex()
    # Best-effort here — we're only narrowing the location dropdown; the
    # authoritative validation happens via ``services.create_equipment``
    # (or ``update_equipment``) below.
    selected_client_id = _safe_query_hex(selected_client_hex)
    _populate_equipment_choices(form, selected_client_id=selected_client_id)

    if request.method == "GET":
        form.client_id.data = eq.client_id.hex()
        form.location_id.data = eq.location_id.hex() if eq.location_id else ""
        form.equipment_model_id.data = eq.equipment_model_id.hex() if eq.equipment_model_id else ""
        form.controller_type_id.data = eq.controller_type_id.hex() if eq.controller_type_id else ""

    if form.validate_on_submit():
        try:
            services.update_equipment(
                db.session,
                eq,
                client_id=bytes.fromhex(form.client_id.data or ""),
                location_id=_hex_or_none(form.location_id.data),
                equipment_model_id=_hex_or_none(form.equipment_model_id.data),
                controller_type_id=_hex_or_none(form.controller_type_id.data),
                serial_number=form.serial_number.data or "",
                asset_tag=form.asset_tag.data or "",
                install_date=form.install_date.data,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Equipment updated."), "success")
            return redirect(url_for("equipment.detail", equipment_hex=equipment_hex))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template("equipment/edit.html", form=form, equipment=eq, tok=_tok())


class _EquipmentFormBundle:
    """Lightweight ``obj=`` source for :class:`EquipmentForm`.

    ``WTForms`` ``populate_obj`` / form ``obj=`` walks attributes by
    name; equipment's FK columns are ``bytes`` but the form fields are
    string-typed ``SelectField`` choices. We adapt with this shim so we
    can keep the form pure WTForms.
    """

    def __init__(self, eq: Equipment) -> None:
        self.serial_number = eq.serial_number
        self.asset_tag = eq.asset_tag
        self.install_date = eq.install_date
        self.notes = eq.notes


def _form_data_for_equipment(eq: Equipment) -> _EquipmentFormBundle:
    return _EquipmentFormBundle(eq)


@bp.route("/<equipment_hex>/deactivate", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def deactivate(equipment_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))
    services.deactivate_equipment(db.session, eq)
    db.session.commit()
    flash(_("Equipment deactivated."), "success")
    return redirect(url_for("equipment.detail", equipment_hex=equipment_hex))


@bp.route("/<equipment_hex>/reactivate", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def reactivate(equipment_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))
    services.reactivate_equipment(db.session, eq)
    db.session.commit()
    flash(_("Equipment reactivated."), "success")
    return redirect(url_for("equipment.detail", equipment_hex=equipment_hex))


# ── Warranties ───────────────────────────────────────────────────────────────


@bp.route("/<equipment_hex>/warranties", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def warranty_create(equipment_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))
    form = forms.WarrantyForm(prefix="warranty")
    if form.validate_on_submit():
        try:
            services.create_warranty(
                db.session,
                equipment_id=eq.id,
                starts_on=form.starts_on.data,
                ends_on=form.ends_on.data,
                reference=form.reference.data or "",
                provider=form.provider.data or "",
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Warranty added."), "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("equipment.detail", equipment_hex=equipment_hex, tab="warranties"))


@bp.route("/<equipment_hex>/warranties/<warranty_hex>", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def warranty_update(equipment_hex: str, warranty_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))
    try:
        w = services.require_warranty(db.session, warranty_hex, eq)
    except ValueError:
        flash(_("Warranty not found."), "error")
        return redirect(url_for("equipment.detail", equipment_hex=equipment_hex, tab="warranties"))
    form = forms.WarrantyForm(prefix="warranty")
    if form.validate_on_submit():
        try:
            services.update_warranty(
                db.session,
                w,
                starts_on=form.starts_on.data,
                ends_on=form.ends_on.data,
                reference=form.reference.data or "",
                provider=form.provider.data or "",
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Warranty updated."), "success")
            return redirect(
                url_for("equipment.detail", equipment_hex=equipment_hex, tab="warranties")
            )
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(
        url_for(
            "equipment.detail",
            equipment_hex=equipment_hex,
            tab="warranties",
            edit_warranty=warranty_hex,
        )
    )


@bp.route("/<equipment_hex>/warranties/<warranty_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def warranty_delete(equipment_hex: str, warranty_hex: str) -> Any:
    try:
        eq = services.require_equipment(db.session, equipment_hex)
    except ValueError:
        flash(_("Equipment not found."), "error")
        return redirect(url_for("equipment.list_equipment"))
    try:
        w = services.require_warranty(db.session, warranty_hex, eq)
    except ValueError:
        flash(_("Warranty not found."), "error")
        return redirect(url_for("equipment.detail", equipment_hex=equipment_hex, tab="warranties"))
    services.delete_warranty(db.session, w)
    db.session.commit()
    flash(_("Warranty deleted."), "success")
    return redirect(url_for("equipment.detail", equipment_hex=equipment_hex, tab="warranties"))


# ── Lookups: controller types ────────────────────────────────────────────────


@bp.route("/controllers")
@login_required  # type: ignore[untyped-decorator]
def list_controllers() -> Any:
    items = services.list_controller_types(db.session)
    return render_template("equipment/controllers_list.html", items=items, tok=_tok())


@bp.route("/controllers/new", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def controller_create() -> Any:
    form = forms.ControllerTypeForm()
    if form.validate_on_submit():
        # Wrap the write in a SAVEPOINT so an IntegrityError (duplicate
        # ``code``) only undoes this insert — not the rest of the request's
        # session work. Without the nested block, ``rollback()`` would
        # discard the outer transaction the test fixture relies on.
        try:
            with db.session.begin_nested():
                services.create_controller_type(
                    db.session,
                    code=form.code.data or "",
                    name=form.name.data or "",
                    notes=form.notes.data or "",
                )
            db.session.commit()
            flash(_("Controller type added."), "success")
        except IntegrityError:
            flash(_("A controller type with that code already exists."), "error")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("equipment.list_controllers"))


@bp.route("/controllers/<controller_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def controller_delete(controller_hex: str) -> Any:
    try:
        ctrl = services.require_controller_type(db.session, controller_hex)
    except ValueError:
        flash(_("Controller type not found."), "error")
        return redirect(url_for("equipment.list_controllers"))
    services.delete_controller_type(db.session, ctrl)
    db.session.commit()
    flash(_("Controller type deleted."), "success")
    return redirect(url_for("equipment.list_controllers"))


# ── Lookups: equipment models ────────────────────────────────────────────────


@bp.route("/models")
@login_required  # type: ignore[untyped-decorator]
def list_models() -> Any:
    items = services.list_equipment_models(db.session)
    form = forms.EquipmentModelForm()
    _populate_model_choices(form)
    return render_template("equipment/models_list.html", items=items, form=form, tok=_tok())


@bp.route("/models/new", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def model_create() -> Any:
    form = forms.EquipmentModelForm()
    _populate_model_choices(form)
    if form.validate_on_submit():
        try:
            with db.session.begin_nested():
                services.create_equipment_model(
                    db.session,
                    manufacturer=form.manufacturer.data or "",
                    model_code=form.model_code.data or "",
                    display_name=form.display_name.data or "",
                    controller_type_id=_hex_or_none(form.controller_type_id.data),
                    notes=form.notes.data or "",
                )
            db.session.commit()
            flash(_("Equipment model added."), "success")
        except IntegrityError:
            flash(
                _("An equipment model with that manufacturer + code already exists."),
                "error",
            )
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("equipment.list_models"))


@bp.route("/models/<model_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def model_delete(model_hex: str) -> Any:
    try:
        mdl = services.require_equipment_model(db.session, model_hex)
    except ValueError:
        flash(_("Equipment model not found."), "error")
        return redirect(url_for("equipment.list_models"))
    services.delete_equipment_model(db.session, mdl)
    db.session.commit()
    flash(_("Equipment model deleted."), "success")
    return redirect(url_for("equipment.list_models"))


# ── CSV imports ──────────────────────────────────────────────────────────────


@bp.route("/import", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def import_equipment() -> Any:
    form = forms.ImportCsvForm()
    if form.validate_on_submit():
        raw = form.csv_file.data.read().decode("utf-8", errors="replace")
        imported, errors = _run_import(services.import_equipment_csv, raw)
        if imported:
            flash(_("%(count)s equipment imported.", count=imported), "success")
        for err in errors:
            flash(err, "error")
        if not errors:
            return redirect(url_for("equipment.list_equipment"))
    return render_template(
        "equipment/import.html",
        form=form,
        tok=_tok(),
        kind="equipment",
        title=_("Import equipment"),
        columns=_(
            "Expected columns: client_name (required), location_label, "
            "manufacturer, model_code, controller_code, serial_number, "
            "asset_tag, install_date (YYYY-MM-DD), notes"
        ),
        action=url_for("equipment.import_equipment"),
    )


@bp.route("/controllers/import", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def import_controllers() -> Any:
    form = forms.ImportCsvForm()
    if form.validate_on_submit():
        raw = form.csv_file.data.read().decode("utf-8", errors="replace")
        imported, errors = _run_import(services.import_controller_types_csv, raw)
        if imported:
            flash(_("%(count)s controller types imported.", count=imported), "success")
        for err in errors:
            flash(err, "error")
        if not errors:
            return redirect(url_for("equipment.list_controllers"))
    return render_template(
        "equipment/import.html",
        form=form,
        tok=_tok(),
        kind="controllers",
        title=_("Import controller types"),
        columns=_("Expected columns: code (required), name (required), notes"),
        action=url_for("equipment.import_controllers"),
    )


@bp.route("/models/import", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def import_models() -> Any:
    form = forms.ImportCsvForm()
    if form.validate_on_submit():
        raw = form.csv_file.data.read().decode("utf-8", errors="replace")
        imported, errors = _run_import(services.import_equipment_models_csv, raw)
        if imported:
            flash(_("%(count)s equipment models imported.", count=imported), "success")
        for err in errors:
            flash(err, "error")
        if not errors:
            return redirect(url_for("equipment.list_models"))
    return render_template(
        "equipment/import.html",
        form=form,
        tok=_tok(),
        kind="models",
        title=_("Import equipment models"),
        columns=_(
            "Expected columns: manufacturer (required), model_code (required), "
            "display_name, controller_code, notes"
        ),
        action=url_for("equipment.import_models"),
    )


def _run_import(import_fn: Any, raw: str) -> tuple[int, list[str]]:
    """Run a CSV import inside a SAVEPOINT so any half-applied state on
    a complete failure rolls back without affecting the rest of the
    request session."""
    nested = db.session.begin_nested()
    imported, errors = import_fn(db.session, raw)
    if imported:
        nested.commit()
        db.session.commit()
    else:
        nested.rollback()
    return imported, errors


__all__ = ["bp"]
