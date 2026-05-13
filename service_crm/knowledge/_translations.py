"""Translatable string registry for the knowledge blueprint.

Mirrors :mod:`service_crm.tickets._translations`. The labels for
checklist-item kinds are stable English codes (``bool``, ``text``,
``number``, ``choice``); display strings translate via this registry
so ``pybabel extract`` picks them up.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

CHECKLIST_KIND_LABELS: dict[str, object] = {
    "bool": _l("Yes / no"),
    "text": _l("Text"),
    "number": _l("Number"),
    "choice": _l("Choice"),
}


def kind_label(code: str) -> str:
    label = CHECKLIST_KIND_LABELS.get(code)
    return str(label) if label is not None else code


__all__ = ["CHECKLIST_KIND_LABELS", "kind_label"]
