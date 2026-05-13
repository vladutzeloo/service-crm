"""Translatable string registry for intervention-domain labels.

Used by templates / forms / flash messages introduced in v0.6 alongside
``service_crm.tickets._translations``.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l

FINDING_KIND_LABELS: dict[str, object] = {
    "observation": _l("Observation"),
    "root_cause": _l("Root cause"),
}


def finding_kind_label(is_root_cause: bool) -> str:
    key = "root_cause" if is_root_cause else "observation"
    label = FINDING_KIND_LABELS[key]
    return str(label)


__all__ = ["FINDING_KIND_LABELS", "finding_kind_label"]
