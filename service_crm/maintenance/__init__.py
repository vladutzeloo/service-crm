"""Maintenance blueprint — ROADMAP 0.7.0.

Owns the preventive-maintenance domain:

- :class:`MaintenanceTemplate` — reusable recipe (cadence + estimated
  time + optional :class:`ChecklistTemplate` linkage).
- :class:`MaintenancePlan` — per-equipment schedule
  (``cadence_days``, ``last_done_on``, ``next_due_on``).
- :class:`MaintenanceTask` — generated due-task instance from a plan.
- :class:`MaintenanceExecution` — completed task linked back to a
  :class:`ServiceIntervention`.

Mounted under ``/maintenance``. The APScheduler bootstrap in
:mod:`service_crm.shared.scheduler` calls into
:func:`services.scheduler_tick` to recompute ``next_due_on`` on every
active plan and generate the next pending task.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "maintenance",
    __name__,
    url_prefix="/maintenance",
    template_folder="../templates/maintenance",
)

from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
