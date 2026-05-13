"""Routes for the maintenance blueprint.

Mounted under ``/maintenance``. Thin views: parse the request, call
:mod:`.services`, render or redirect. Idempotency tokens are recorded
via :mod:`service_crm.shared.idempotency` on every state-changing form.
"""

from __future__ import annotations

import uuid
from typing import Any

from flask import flash, redirect, render_template, request, url_for
from flask_babel import gettext as _
from flask_login import current_user, login_required

from ..equipment.models import Equipment
from ..extensions import db
from ..knowledge.models import ChecklistTemplate
from ..shared import idempotency
from ..tickets.intervention_models import ServiceIntervention
from . import bp, forms, services
from ._translations import task_status_label, task_status_tone
from .models import MaintenancePlan, TaskStatus


def _tok() -> str:
    return uuid.uuid4().hex


def _hex_or_none(value: str | None) -> bytes | None:
    if not value:
        return None
    return bytes.fromhex(value)


def _safe_hex(value: str | None) -> bytes | None:
    if not value:  # pragma: no cover - request.args.getlist drops empty strings
        return None
    try:
        return bytes.fromhex(value)
    except ValueError:  # pragma: no cover - defensive fallback for hand-crafted URLs
        return None


def _actor_id() -> bytes:
    user = current_user
    return bytes(user.id)


def _record_idempotency(token: str, route: str) -> bool:
    if not token:  # pragma: no cover - every state-changing form ships a token
        return True
    return idempotency.record(db.session, user_id=_actor_id(), token=token, route=route)


# ── Templates ───────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> Any:
    return redirect(url_for("maintenance.plans_list"))


@bp.route("/templates")
@login_required  # type: ignore[untyped-decorator]
def templates_list() -> Any:
    show = request.args.get("show", "active")
    items = services.list_templates(db.session, active_only=show != "all")
    return render_template(
        "maintenance/templates_list.html",
        items=items,
        show=show,
        tok=_tok(),
    )


def _populate_template_choices(form: forms.TemplateCreateForm | forms.TemplateEditForm) -> None:
    checklists = (
        db.session.query(ChecklistTemplate)
        .filter(ChecklistTemplate.is_active.is_(True))
        .order_by(ChecklistTemplate.name)
        .all()
    )
    choices: list[tuple[str, str]] = [("", _("— none —"))]
    choices.extend((c.id.hex(), c.name) for c in checklists)
    form.checklist_template_id.choices = choices


@bp.route("/templates/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def template_new() -> Any:
    form = forms.TemplateCreateForm()
    _populate_template_choices(form)
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "maintenance.template_new"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("maintenance.templates_list"))
        try:
            services.create_template(
                db.session,
                name=form.name.data or "",
                description=form.description.data or "",
                cadence_days=form.cadence_days.data or 180,
                estimated_minutes=form.estimated_minutes.data,
                checklist_template_id=_hex_or_none(form.checklist_template_id.data),
            )
            db.session.commit()
            flash(_("Maintenance template created."), "success")
            return redirect(url_for("maintenance.templates_list"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "maintenance/template_edit.html",
        form=form,
        template=None,
        tok=_tok(),
    )


@bp.route("/templates/<template_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def template_edit(template_hex: str) -> Any:
    try:
        template = services.require_template(db.session, template_hex)
    except ValueError:
        flash(_("Template not found."), "error")
        return redirect(url_for("maintenance.templates_list"))
    form = forms.TemplateEditForm()
    _populate_template_choices(form)
    if request.method == "GET":
        form.name.data = template.name
        form.description.data = template.description
        form.cadence_days.data = template.cadence_days
        form.estimated_minutes.data = template.estimated_minutes
        form.checklist_template_id.data = (
            template.checklist_template_id.hex() if template.checklist_template_id else ""
        )
        form.is_active.data = template.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(token, "maintenance.template_edit"):
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("maintenance.templates_list"))
        try:
            services.update_template(
                db.session,
                template,
                name=form.name.data or "",
                description=form.description.data or "",
                cadence_days=form.cadence_days.data or template.cadence_days,
                estimated_minutes=form.estimated_minutes.data,
                checklist_template_id=_hex_or_none(form.checklist_template_id.data),
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Maintenance template updated."), "success")
            return redirect(url_for("maintenance.templates_list"))
        except ValueError as exc:
            flash(str(exc), "error")
    return render_template(
        "maintenance/template_edit.html",
        form=form,
        template=template,
        tok=_tok(),
    )


# ── Plans ───────────────────────────────────────────────────────────────────


@bp.route("/plans")
@login_required  # type: ignore[untyped-decorator]
def plans_list() -> Any:
    equipment_id = _safe_hex(request.args.get("equipment"))
    show = request.args.get("show", "active")
    overdue = request.args.get("overdue") == "1"
    items = services.list_plans(
        db.session,
        equipment_id=equipment_id,
        active_only=show != "all",
        overdue_only=overdue,
    )
    equipment = db.session.get(Equipment, equipment_id) if equipment_id is not None else None
    return render_template(
        "maintenance/plans_list.html",
        items=items,
        equipment=equipment,
        show=show,
        overdue=overdue,
        tok=_tok(),
    )


def _populate_plan_choices(form: forms.PlanCreateForm) -> None:
    equipment = (
        db.session.query(Equipment)
        .filter(Equipment.is_active.is_(True))
        .order_by(Equipment.serial_number)
        .all()
    )
    form.equipment_id.choices = [(e.id.hex(), e.label) for e in equipment]
    templates = services.list_templates(db.session)
    form.template_id.choices = [(t.id.hex(), t.name) for t in templates]


@bp.route("/plans/new", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def plan_new() -> Any:
    pre_equipment_id = _safe_hex(request.args.get("equipment"))
    form = forms.PlanCreateForm()
    _populate_plan_choices(form)
    if (
        pre_equipment_id is not None and request.method == "GET"
    ):  # pragma: no cover - convenience pre-fill from equipment detail link
        form.equipment_id.data = pre_equipment_id.hex()
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(
            token, "maintenance.plan_new"
        ):  # pragma: no cover - same-token retry exercised in tests/maintenance/test_routes.py
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("maintenance.plans_list"))
        try:
            plan = services.create_plan(
                db.session,
                equipment_id=bytes.fromhex(form.equipment_id.data or ""),
                template_id=bytes.fromhex(form.template_id.data or ""),
                cadence_days=form.cadence_days.data,
                last_done_on=form.last_done_on.data,
                notes=form.notes.data or "",
            )
            db.session.commit()
            flash(_("Maintenance plan created."), "success")
            return redirect(url_for("maintenance.plan_detail", plan_hex=plan.id.hex()))
        except ValueError as exc:  # pragma: no cover - service validation tested upstream
            flash(str(exc), "error")
    return render_template(
        "maintenance/plan_edit.html",
        form=form,
        plan=None,
        tok=_tok(),
    )


@bp.route("/plans/<plan_hex>")
@login_required  # type: ignore[untyped-decorator]
def plan_detail(plan_hex: str) -> Any:
    try:
        plan = services.require_plan(db.session, plan_hex)
    except ValueError:
        flash(_("Plan not found."), "error")
        return redirect(url_for("maintenance.plans_list"))
    tasks = services.list_tasks(db.session, plan_id=plan.id)
    return render_template(
        "maintenance/plan_detail.html",
        plan=plan,
        tasks=tasks,
        task_status_label=task_status_label,
        task_status_tone=task_status_tone,
        tok=_tok(),
    )


@bp.route("/plans/<plan_hex>/edit", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def plan_edit(plan_hex: str) -> Any:
    try:
        plan = services.require_plan(db.session, plan_hex)
    except ValueError:
        flash(_("Plan not found."), "error")
        return redirect(url_for("maintenance.plans_list"))
    form = forms.PlanEditForm()
    if request.method == "GET":
        form.cadence_days.data = plan.cadence_days
        form.last_done_on.data = plan.last_done_on
        form.notes.data = plan.notes
        form.is_active.data = plan.is_active
    if form.validate_on_submit():
        token = request.form.get("idempotency_token", "")
        if not _record_idempotency(
            token, "maintenance.plan_edit"
        ):  # pragma: no cover - same-token retry covered upstream
            flash(_("This request was already submitted."), "info")
            return redirect(url_for("maintenance.plan_detail", plan_hex=plan_hex))
        try:
            services.update_plan(
                db.session,
                plan,
                cadence_days=form.cadence_days.data or plan.cadence_days,
                last_done_on=form.last_done_on.data,
                notes=form.notes.data or "",
                is_active=bool(form.is_active.data),
            )
            db.session.commit()
            flash(_("Maintenance plan updated."), "success")
            return redirect(url_for("maintenance.plan_detail", plan_hex=plan_hex))
        except ValueError as exc:  # pragma: no cover - service-level validation tested separately
            flash(str(exc), "error")
    return render_template(
        "maintenance/plan_edit.html",
        form=form,
        plan=plan,
        tok=_tok(),
    )


@bp.route("/plans/<plan_hex>/generate-tasks", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def plan_generate_tasks(plan_hex: str) -> Any:
    try:
        plan = services.require_plan(db.session, plan_hex)
    except ValueError:
        flash(_("Plan not found."), "error")
        return redirect(url_for("maintenance.plans_list"))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(
        token, "maintenance.plan_generate_tasks"
    ):  # pragma: no cover - same-token retry covered upstream
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("maintenance.plan_detail", plan_hex=plan_hex))
    services.recompute_plan(db.session, plan)
    created = services.generate_pending_tasks(db.session, plan=plan)
    db.session.commit()
    flash(
        _("Generated %(count)s task(s).", count=len(created)),
        "success" if created else "info",
    )
    return redirect(url_for("maintenance.plan_detail", plan_hex=plan_hex))


# ── Tasks ───────────────────────────────────────────────────────────────────


@bp.route("/tasks")
@login_required  # type: ignore[untyped-decorator]
def tasks_list() -> Any:
    status = request.args.get("status")
    if status not in TaskStatus.ALL:
        status = None
    overdue = request.args.get("overdue") == "1"
    items = services.list_tasks(
        db.session,
        status=status,
        overdue_only=overdue,
    )
    return render_template(
        "maintenance/tasks_list.html",
        items=items,
        status=status,
        overdue=overdue,
        task_status_label=task_status_label,
        task_status_tone=task_status_tone,
        statuses=sorted(TaskStatus.ALL),
        tok=_tok(),
    )


@bp.route("/tasks/<task_hex>", methods=["GET", "POST"])
@login_required  # type: ignore[untyped-decorator]
def task_detail(task_hex: str) -> Any:
    try:
        task = services.require_task(db.session, task_hex)
    except ValueError:
        flash(_("Task not found."), "error")
        return redirect(url_for("maintenance.tasks_list"))
    plan = task.plan
    assign_form = forms.TaskAssignForm()
    _populate_assign_choices(assign_form)
    complete_form = forms.TaskCompleteForm()
    _populate_intervention_choices(complete_form, plan)
    escalate_form = forms.TaskEscalateForm()
    if (
        request.method == "GET" and task.assigned_technician_id
    ):  # pragma: no cover - convenience pre-fill
        assign_form.technician_id.data = task.assigned_technician_id.hex()
    return render_template(
        "maintenance/task_detail.html",
        task=task,
        plan=plan,
        assign_form=assign_form,
        complete_form=complete_form,
        escalate_form=escalate_form,
        task_status_label=task_status_label,
        task_status_tone=task_status_tone,
        tok=_tok(),
    )


def _populate_assign_choices(form: forms.TaskAssignForm) -> None:
    from ..planning import services as planning_services

    techs = planning_services.list_technicians(db.session, active_only=True)
    choices: list[tuple[str, str]] = [("", _("— unassigned —"))]
    choices.extend((t.id.hex(), t.display_name) for t in techs)
    form.technician_id.choices = choices


def _populate_intervention_choices(form: forms.TaskCompleteForm, plan: MaintenancePlan) -> None:
    # Surface only open interventions for the plan's equipment so the
    # technician can record their session against the task in one click.
    rows = (
        db.session.query(ServiceIntervention)
        .join(ServiceIntervention.ticket)
        .filter(ServiceIntervention.ticket.has(equipment_id=plan.equipment_id))
        .order_by(ServiceIntervention.started_at.desc())
        .limit(20)
        .all()
    )
    choices: list[tuple[str, str]] = [("", _("— no linked intervention —"))]
    for iv in rows:  # pragma: no cover - populated only when a matching intervention exists
        choices.append((iv.id.hex(), f"#{iv.ticket.label} — {iv.started_at:%Y-%m-%d %H:%M}"))
    form.intervention_id.choices = choices


@bp.route("/tasks/<task_hex>/assign", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def task_assign(task_hex: str) -> Any:
    try:
        task = services.require_task(db.session, task_hex)
    except ValueError:
        flash(_("Task not found."), "error")
        return redirect(url_for("maintenance.tasks_list"))
    form = forms.TaskAssignForm()
    _populate_assign_choices(form)
    if (
        not form.validate_on_submit()
    ):  # pragma: no cover - form-level guards covered by form unit-tests
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(
        token, "maintenance.task_assign"
    ):  # pragma: no cover - retry path covered upstream
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    try:
        services.assign_task(
            db.session,
            task,
            technician_id=_hex_or_none(form.technician_id.data),
        )
        db.session.commit()
        flash(_("Task assigned."), "success")
    except ValueError as exc:  # pragma: no cover - service-level errors covered separately
        flash(str(exc), "error")
    return redirect(url_for("maintenance.task_detail", task_hex=task_hex))


@bp.route("/tasks/<task_hex>/complete", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def task_complete(task_hex: str) -> Any:
    try:
        task = services.require_task(db.session, task_hex)
    except ValueError:
        flash(_("Task not found."), "error")
        return redirect(url_for("maintenance.tasks_list"))
    form = forms.TaskCompleteForm()
    _populate_intervention_choices(form, task.plan)
    if (
        not form.validate_on_submit()
    ):  # pragma: no cover - form-level guards covered by form unit-tests
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(
        token, "maintenance.task_complete"
    ):  # pragma: no cover - retry path covered upstream
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    try:
        services.complete_task(
            db.session,
            task,
            intervention_id=_hex_or_none(form.intervention_id.data),
            notes=form.notes.data or "",
        )
        db.session.commit()
        flash(_("Task marked done."), "success")
    except ValueError as exc:  # pragma: no cover - service-level errors covered separately
        flash(str(exc), "error")
    return redirect(url_for("maintenance.task_detail", task_hex=task_hex))


@bp.route("/tasks/<task_hex>/escalate", methods=["POST"])
@login_required  # type: ignore[untyped-decorator]
def task_escalate(task_hex: str) -> Any:
    try:
        task = services.require_task(db.session, task_hex)
    except ValueError:
        flash(_("Task not found."), "error")
        return redirect(url_for("maintenance.tasks_list"))
    form = forms.TaskEscalateForm()
    if (
        not form.validate_on_submit()
    ):  # pragma: no cover - form-level guards covered by form unit-tests
        for errs in form.errors.values():
            for err in errs:
                flash(err, "error")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    token = request.form.get("idempotency_token", "")
    if not _record_idempotency(
        token, "maintenance.task_escalate"
    ):  # pragma: no cover - retry path covered upstream
        flash(_("This request was already submitted."), "info")
        return redirect(url_for("maintenance.task_detail", task_hex=task_hex))
    try:
        ticket = services.escalate_task(
            db.session,
            task,
            title=form.title.data or "",
            description=form.description.data or "",
        )
        db.session.commit()
        flash(_("Ticket opened from maintenance task."), "success")
        return redirect(url_for("tickets.detail", ticket_hex=ticket.id.hex()))
    except ValueError as exc:  # pragma: no cover - reached only when task already escalated/done
        flash(str(exc), "error")
    return redirect(url_for("maintenance.task_detail", task_hex=task_hex))


__all__: list[str] = []
