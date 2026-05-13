"""Routes for the dashboard blueprint.

Two surfaces, both read-only:

- ``/`` (``dashboard.admin``) — manager view.
- ``/dashboard/me`` (``dashboard.me``) — technician view.

The cross-link between them lives in the templates: the manager view
has a "My queue" pill leading to ``dashboard.me``, the technician
view has a "Manager overview" link leading back to ``dashboard.admin``.
"""

from __future__ import annotations

from typing import Any

from flask import render_template
from flask_login import current_user, login_required

from ..extensions import db
from ..planning import services as planning_services
from ..tickets._translations import (
    priority_label,
    priority_tone,
    status_label,
    status_tone,
    type_label,
)
from . import bp, services
from ._translations import kpi_label, panel_label


def _template_helpers() -> dict[str, Any]:
    return {
        "kpi_label": kpi_label,
        "panel_label": panel_label,
        "status_label": status_label,
        "status_tone": status_tone,
        "type_label": type_label,
        "priority_label": priority_label,
        "priority_tone": priority_tone,
    }


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def admin() -> Any:
    """Manager dashboard — KPI tiles + secondary panels."""
    window = services.default_window()
    kpis = services.manager_kpis(db.session)
    by_status = services.tickets_by_status(db.session)
    upcoming = services.upcoming_maintenance(db.session)
    recent = services.recent_interventions(db.session)
    high_risk = services.high_risk_machines(db.session, window=window)
    tech_load = services.technician_load_week(db.session)
    return render_template(
        "dashboard/admin.html",
        kpis=kpis,
        tickets_by_status=by_status,
        upcoming_maintenance=upcoming,
        recent_interventions=recent,
        high_risk_machines=high_risk,
        technician_load=tech_load,
        window=window,
        **_template_helpers(),
    )


@bp.route("/dashboard/me")
@login_required  # type: ignore[untyped-decorator]
def me() -> Any:
    """Technician dashboard — today's queue, no left sidebar."""
    user_id = bytes(current_user.id)
    technician = planning_services.require_technician_for_user(db.session, user_id)
    technician_id = technician.id if technician is not None else None
    summary = services.technician_summary(db.session, user_id=user_id, technician_id=technician_id)
    open_tickets = services.my_open_tickets(db.session, user_id=user_id)
    overdue_tickets = services.my_overdue_tickets(db.session, user_id=user_id)
    tasks = services.my_maintenance_tasks(db.session, technician_id=technician_id)
    return render_template(
        "dashboard/me.html",
        technician=technician,
        summary=summary,
        open_tickets=open_tickets,
        overdue_tickets=overdue_tickets,
        tasks=tasks,
        **_template_helpers(),
    )


__all__: list[str] = []
