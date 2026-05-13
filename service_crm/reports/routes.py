"""Routes for the reports blueprint.

Two routes per report:

- ``GET /reports/<code>`` — HTML view (table + filter bar).
- ``GET /reports/<code>.csv`` — CSV export, same data.

Filters come from query args; no form posts. All routes are
``@login_required``; role-based gating waits for v0.9.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Any

from flask import render_template, request
from flask_login import login_required

from ..extensions import db
from ..shared.date_window import DateWindow, parse_window
from ..tickets._translations import status_label, status_tone
from . import bp, services
from ._translations import (
    REPORT_CODES,
    period_label,
    report_description,
    report_label,
)
from .csv import write_csv


def _window_from_request() -> DateWindow:
    return parse_window(request.args)


# ── Index ────────────────────────────────────────────────────────────────────


@bp.route("/")
@login_required  # type: ignore[untyped-decorator]
def index() -> Any:
    window = _window_from_request()
    catalog = [
        {
            "code": code,
            "label": report_label(code),
            "description": report_description(code),
            "html_endpoint": f"reports.{code}",
            "csv_endpoint": f"reports.{code}_csv",
        }
        for code in REPORT_CODES
    ]
    return render_template(
        "reports/index.html",
        catalog=catalog,
        window=window,
    )


# ── 1. tickets_by_status ─────────────────────────────────────────────────────


def _build_tickets_by_status(window: DateWindow) -> services.ReportResult:
    return services.tickets_by_status(
        db.session,
        window=window,
        status_label=status_label,
        period_label=period_label,
    )


@bp.route("/tickets_by_status")
@login_required  # type: ignore[untyped-decorator]
def tickets_by_status() -> Any:
    window = _window_from_request()
    result = _build_tickets_by_status(window)
    return render_template(
        "reports/tickets_by_status.html",
        result=result,
        window=window,
        report_code="tickets_by_status",
        report_title=report_label("tickets_by_status"),
        status_label=status_label,
        status_tone=status_tone,
    )


@bp.route("/tickets_by_status.csv")
@login_required  # type: ignore[untyped-decorator]
def tickets_by_status_csv() -> Any:
    window = _window_from_request()
    result = _build_tickets_by_status(window)
    return _csv_response("tickets_by_status", window, result)


# ── 2. interventions_by_machine ──────────────────────────────────────────────


@bp.route("/interventions_by_machine")
@login_required  # type: ignore[untyped-decorator]
def interventions_by_machine() -> Any:
    window = _window_from_request()
    result = services.interventions_by_machine(db.session, window=window)
    return render_template(
        "reports/interventions_by_machine.html",
        result=result,
        window=window,
        report_code="interventions_by_machine",
        report_title=report_label("interventions_by_machine"),
    )


@bp.route("/interventions_by_machine.csv")
@login_required  # type: ignore[untyped-decorator]
def interventions_by_machine_csv() -> Any:
    window = _window_from_request()
    result = services.interventions_by_machine(db.session, window=window)
    return _csv_response("interventions_by_machine", window, result)


# ── 3. parts_used ────────────────────────────────────────────────────────────


@bp.route("/parts_used")
@login_required  # type: ignore[untyped-decorator]
def parts_used() -> Any:
    window = _window_from_request()
    result = services.parts_used(db.session, window=window)
    return render_template(
        "reports/parts_used.html",
        result=result,
        window=window,
        report_code="parts_used",
        report_title=report_label("parts_used"),
    )


@bp.route("/parts_used.csv")
@login_required  # type: ignore[untyped-decorator]
def parts_used_csv() -> Any:
    window = _window_from_request()
    result = services.parts_used(db.session, window=window)
    return _csv_response("parts_used", window, result)


# ── 4. maintenance_due_vs_completed ──────────────────────────────────────────


def _build_maintenance(window: DateWindow) -> services.ReportResult:
    return services.maintenance_due_vs_completed(
        db.session,
        window=window,
        period_label=period_label,
    )


@bp.route("/maintenance_due_vs_completed")
@login_required  # type: ignore[untyped-decorator]
def maintenance_due_vs_completed() -> Any:
    window = _window_from_request()
    result = _build_maintenance(window)
    return render_template(
        "reports/maintenance_due_vs_completed.html",
        result=result,
        window=window,
        report_code="maintenance_due_vs_completed",
        report_title=report_label("maintenance_due_vs_completed"),
    )


@bp.route("/maintenance_due_vs_completed.csv")
@login_required  # type: ignore[untyped-decorator]
def maintenance_due_vs_completed_csv() -> Any:
    window = _window_from_request()
    result = _build_maintenance(window)
    return _csv_response("maintenance_due_vs_completed", window, result)


# ── 5. technician_workload ───────────────────────────────────────────────────


@bp.route("/technician_workload")
@login_required  # type: ignore[untyped-decorator]
def technician_workload() -> Any:
    window = _window_from_request()
    result = services.technician_workload(db.session, window=window)
    return render_template(
        "reports/technician_workload.html",
        result=result,
        window=window,
        report_code="technician_workload",
        report_title=report_label("technician_workload"),
    )


@bp.route("/technician_workload.csv")
@login_required  # type: ignore[untyped-decorator]
def technician_workload_csv() -> Any:
    window = _window_from_request()
    result = services.technician_workload(db.session, window=window)
    return _csv_response("technician_workload", window, result)


# ── 6. repeat_issues ─────────────────────────────────────────────────────────


@bp.route("/repeat_issues")
@login_required  # type: ignore[untyped-decorator]
def repeat_issues() -> Any:
    window = _window_from_request()
    result = services.repeat_issues(db.session, window=window)
    return render_template(
        "reports/repeat_issues.html",
        result=result,
        window=window,
        report_code="repeat_issues",
        report_title=report_label("repeat_issues"),
    )


@bp.route("/repeat_issues.csv")
@login_required  # type: ignore[untyped-decorator]
def repeat_issues_csv() -> Any:
    window = _window_from_request()
    result = services.repeat_issues(db.session, window=window)
    return _csv_response("repeat_issues", window, result)


# ── Helpers ──────────────────────────────────────────────────────────────────


def _csv_response(
    report_code: str,
    window: DateWindow,
    result: services.ReportResult,
) -> Any:
    rows: list[Sequence[Any]] = [r for r in result.rows]
    if result.total_row is not None:
        rows.append(result.total_row)
    return write_csv(
        report_code=report_code,
        window=window,
        headers=result.headers,
        rows=rows,
    )


__all__: list[str] = []
