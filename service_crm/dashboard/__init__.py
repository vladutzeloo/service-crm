"""Dashboard blueprint — ROADMAP 0.8.0.

Operational read views over the v0.7 schema. Two surfaces, one
blueprint per the architecture-plan §6 approval record:

- ``/`` (``dashboard.admin``) — manager view: KPI tiles + secondary
  panels modelled on ``oee-calculator2.0/templates/admin/dashboard.html``.
- ``/dashboard/me`` (``dashboard.me``) — technician view: today's
  queue, no left sidebar, modelled on
  ``oee-calculator2.0/templates/operator/dashboard.html``.

No models, no migration — every aggregate is a read query over the
existing tables (see :mod:`.services`). Every tile is drillable into
a filtered list elsewhere in the app, per the v0.8 ease-of-use bar.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "dashboard",
    __name__,
    template_folder="../templates/dashboard",
)

from . import routes  # noqa: E402, F401

__all__ = ["bp"]
