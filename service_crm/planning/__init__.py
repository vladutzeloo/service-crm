"""Planning blueprint — ROADMAP 0.7.0.

Owns the technician-roster + capacity surface:

- :class:`Technician` — 1:1 with :class:`User` but separate so planning
  attributes (timezone, capacity) don't bloat ``user_account``.
- :class:`TechnicianAssignment` — joins a technician to a ticket and/or
  intervention. CHECK constraint ensures at least one target.
- :class:`TechnicianCapacitySlot` — declared minutes available on a
  given day; per-shift slots are deferred to v1.3.

Mounted under ``/planning``.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "planning",
    __name__,
    url_prefix="/planning",
    template_folder="../templates/planning",
)

from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
