"""Knowledge blueprint — ROADMAP 0.6.0.

Owns the knowledge artefacts that ride alongside an intervention:

- :class:`ChecklistTemplate` + :class:`ChecklistTemplateItem` —
  admin-managed recipes.
- :class:`ChecklistRun` + :class:`ChecklistRunItem` — frozen
  snapshots per intervention. Template edits never mutate historical
  runs (property-tested).
- :class:`ProcedureDocument` + :class:`ProcedureTag` — searchable
  Markdown documents tagged for navigation.

Mounted under ``/knowledge``.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "knowledge",
    __name__,
    url_prefix="/knowledge",
    template_folder="../templates/knowledge",
)

from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
