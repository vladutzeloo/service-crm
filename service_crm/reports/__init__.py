"""Reports blueprint — ROADMAP 0.8.0.

Six aggregate read views over the v0.7 schema (per
[`docs/blueprint.md`](../../docs/blueprint.md) §14):

- ``tickets_by_status`` — count per status x period bucket.
- ``interventions_by_machine`` — count + total minutes per equipment.
- ``parts_used`` — quantity per part code inside the window.
- ``maintenance_due_vs_completed`` — due-task count vs. execution
  count per period bucket.
- ``technician_workload`` — interventions, minutes, completions per
  technician.
- ``repeat_issues`` — equipment with > 1 ticket inside the window.

Every report ships an HTML table view + a ``/<code>.csv`` sibling.
CSV stays the v1 export format (per [`v1-implementation-goals.md`
§0.8 ease-of-use bar](../../docs/v1-implementation-goals.md#080--operational-dashboard)).

Mounted under ``/reports``. No models, no migration — pure reads.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "reports",
    __name__,
    url_prefix="/reports",
    template_folder="../templates/reports",
)

from . import routes  # noqa: E402, F401

__all__ = ["bp"]
