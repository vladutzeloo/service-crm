"""Client blueprint routes — thin views only.

Every view: parses request → calls services → renders template or redirects.
No SQL, no business rules here.
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import login_required

from ..extensions import db
from . import bp, forms, services


def _tok() -> str:
    """Generate a per-request idempotency token (UUID hex)."""
    return uuid.uuid4().hex


# ── List ──────────────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def list_clients() -> Any:
    q = request.args.get("q", "").strip()
    show = request.args.get("show", "active")
    active_only = show != "all"
    page = max(1, int(request.args.get("page", 1)))

    clients, total = services.list_clients(db.session, q=q, active_only=active_only, page=page)
    return render_template(
        "clients/list.html",
        clients=clients,
        total=total,
        q=q,
        show=show,
        page=page,
    )


# ── Create ────────────────────────────────────────────────────────────────────


@bp.route("/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def new_client() -> Any:
    form = forms.ClientForm()
    if form.validate_on_submit():
        client = services.create_client(
            db.session,
            name=form.name.data or "",
            email=form.email.data or "",
            phone=form.phone.data or "",
            notes=form.notes.data or "",
        )
        db.session.commit()
        flash(_("Client created."), "success")
        return redirect(url_for("clients.detail", client_hex=client.id.hex()))
    return render_template("clients/edit.html", form=form, client=None, tok=_tok())


# ── Detail ────────────────────────────────────────────────────────────────────


@bp.route("/<client_hex>")
@login_required  # type: ignore[untyped-decorator]
def detail(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))

    tab = request.args.get("tab", "contacts")
    edit_contact = request.args.get("edit_contact")
    edit_location = request.args.get("edit_location")
    edit_contract = request.args.get("edit_contract")

    contact_form = forms.ContactForm(prefix="contact")
    location_form = forms.LocationForm(prefix="location")
    contract_form = forms.ContractForm(prefix="contract")

    # Pre-fill edit forms when the query param matches an entity id.
    edit_contact_obj = None
    if edit_contact:
        try:
            edit_contact_obj = services.require_contact(db.session, edit_contact, client)
            contact_form = forms.ContactForm(
                prefix="contact",
                obj=edit_contact_obj,
            )
        except ValueError:
            edit_contact = None

    edit_location_obj = None
    if edit_location:
        try:
            edit_location_obj = services.require_location(db.session, edit_location, client)
            location_form = forms.LocationForm(
                prefix="location",
                obj=edit_location_obj,
            )
        except ValueError:
            edit_location = None

    edit_contract_obj = None
    if edit_contract:
        try:
            edit_contract_obj = services.require_contract(db.session, edit_contract, client)
            contract_form = forms.ContractForm(
                prefix="contract",
                obj=edit_contract_obj,
            )
        except ValueError:
            edit_contract = None

    return render_template(
        "clients/detail.html",
        client=client,
        tab=tab,
        contact_form=contact_form,
        location_form=location_form,
        contract_form=contract_form,
        edit_contact=edit_contact,
        edit_contact_obj=edit_contact_obj,
        edit_location=edit_location,
        edit_location_obj=edit_location_obj,
        edit_contract=edit_contract,
        edit_contract_obj=edit_contract_obj,
        tok=_tok(),
    )


# ── Edit ──────────────────────────────────────────────────────────────────────


@bp.route("/<client_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def edit_client(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))

    form = forms.ClientForm(obj=client)
    if form.validate_on_submit():
        services.update_client(
            db.session,
            client,
            name=form.name.data or "",
            email=form.email.data or "",
            phone=form.phone.data or "",
            notes=form.notes.data or "",
        )
        db.session.commit()
        flash(_("Client updated."), "success")
        return redirect(url_for("clients.detail", client_hex=client_hex))
    return render_template("clients/edit.html", form=form, client=client, tok=_tok())


# ── Activate / Deactivate ─────────────────────────────────────────────────────


@bp.route("/<client_hex>/deactivate", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def deactivate(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    services.deactivate_client(db.session, client)
    db.session.commit()
    flash(_("Client deactivated."), "success")
    return redirect(url_for("clients.detail", client_hex=client_hex))


@bp.route("/<client_hex>/reactivate", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def reactivate(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    services.reactivate_client(db.session, client)
    db.session.commit()
    flash(_("Client reactivated."), "success")
    return redirect(url_for("clients.detail", client_hex=client_hex))


# ── Contacts ──────────────────────────────────────────────────────────────────


@bp.route("/<client_hex>/contacts", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contact_create(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.ContactForm(prefix="contact")
    if form.validate_on_submit():
        services.create_contact(
            db.session,
            client_id=client.id,
            name=form.name.data or "",
            role=form.role.data or "",
            email=form.email.data or "",
            phone=form.phone.data or "",
            is_primary=bool(form.is_primary.data),
        )
        db.session.commit()
        flash(_("Contact added."), "success")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="contacts"))


@bp.route("/<client_hex>/contacts/<contact_hex>", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contact_update(client_hex: str, contact_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        contact = services.require_contact(db.session, contact_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.ContactForm(prefix="contact")
    if form.validate_on_submit():
        services.update_contact(
            db.session,
            contact,
            name=form.name.data or "",
            role=form.role.data or "",
            email=form.email.data or "",
            phone=form.phone.data or "",
            is_primary=bool(form.is_primary.data),
        )
        db.session.commit()
        flash(_("Contact updated."), "success")
        return redirect(url_for("clients.detail", client_hex=client_hex, tab="contacts"))
    for field_errors in form.errors.values():
        for err in field_errors:
            flash(err, "error")
    return redirect(
        url_for(
            "clients.detail",
            client_hex=client_hex,
            tab="contacts",
            edit_contact=contact_hex,
        )
    )


@bp.route("/<client_hex>/contacts/<contact_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contact_delete(client_hex: str, contact_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        contact = services.require_contact(db.session, contact_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    services.delete_contact(db.session, contact)
    db.session.commit()
    flash(_("Contact deleted."), "success")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="contacts"))


# ── Locations ─────────────────────────────────────────────────────────────────


@bp.route("/<client_hex>/locations", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def location_create(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.LocationForm(prefix="location")
    if form.validate_on_submit():
        services.create_location(
            db.session,
            client_id=client.id,
            label=form.label.data or "",
            address=form.address.data or "",
            city=form.city.data or "",
            country=form.country.data or "",
        )
        db.session.commit()
        flash(_("Location added."), "success")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="locations"))


@bp.route("/<client_hex>/locations/<location_hex>", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def location_update(client_hex: str, location_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        location = services.require_location(db.session, location_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.LocationForm(prefix="location")
    if form.validate_on_submit():
        services.update_location(
            db.session,
            location,
            label=form.label.data or "",
            address=form.address.data or "",
            city=form.city.data or "",
            country=form.country.data or "",
        )
        db.session.commit()
        flash(_("Location updated."), "success")
        return redirect(url_for("clients.detail", client_hex=client_hex, tab="locations"))
    for field_errors in form.errors.values():
        for err in field_errors:
            flash(err, "error")
    return redirect(
        url_for(
            "clients.detail",
            client_hex=client_hex,
            tab="locations",
            edit_location=location_hex,
        )
    )


@bp.route("/<client_hex>/locations/<location_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def location_delete(client_hex: str, location_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        location = services.require_location(db.session, location_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    services.delete_location(db.session, location)
    db.session.commit()
    flash(_("Location deleted."), "success")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="locations"))


# ── Contracts ─────────────────────────────────────────────────────────────────


@bp.route("/<client_hex>/contracts", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contract_create(client_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.ContractForm(prefix="contract")
    if form.validate_on_submit():
        try:
            services.create_contract(
                db.session,
                client_id=client.id,
                title=form.title.data or "",
                reference=form.reference.data or "",
                starts_on=form.starts_on.data,
                ends_on=form.ends_on.data or None,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Contract added."), "success")
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="contracts"))


@bp.route("/<client_hex>/contracts/<contract_hex>", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contract_update(client_hex: str, contract_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        contract = services.require_contract(db.session, contract_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    form = forms.ContractForm(prefix="contract")
    if form.validate_on_submit():
        try:
            services.update_contract(
                db.session,
                contract,
                title=form.title.data or "",
                reference=form.reference.data or "",
                starts_on=form.starts_on.data,
                ends_on=form.ends_on.data or None,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Contract updated."), "success")
            return redirect(url_for("clients.detail", client_hex=client_hex, tab="contracts"))
        except ValueError as exc:
            flash(str(exc), "error")
    else:
        for field_errors in form.errors.values():
            for err in field_errors:
                flash(err, "error")
    return redirect(
        url_for(
            "clients.detail",
            client_hex=client_hex,
            tab="contracts",
            edit_contract=contract_hex,
        )
    )


@bp.route("/<client_hex>/contracts/<contract_hex>/delete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def contract_delete(client_hex: str, contract_hex: str) -> Any:
    try:
        client = services.require_client(db.session, client_hex)
        contract = services.require_contract(db.session, contract_hex, client)
    except ValueError:
        flash(_("Client not found."), "error")
        return redirect(url_for("clients.list_clients"))
    services.delete_contract(db.session, contract)
    db.session.commit()
    flash(_("Contract deleted."), "success")
    return redirect(url_for("clients.detail", client_hex=client_hex, tab="contracts"))


# ── CSV import ────────────────────────────────────────────────────────────────


@bp.route("/import", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def import_clients() -> Any:
    form = forms.ImportClientsForm()
    if form.validate_on_submit():
        raw = form.csv_file.data.read().decode("utf-8", errors="replace")
        imported, errors = services.import_clients_csv(db.session, raw)
        if imported:
            db.session.commit()
            flash(_("%(count)s clients imported.", count=imported), "success")
        for err in errors:
            flash(err, "error")
        if not errors:
            return redirect(url_for("clients.list_clients"))
    return render_template("clients/import.html", form=form, tok=_tok())
