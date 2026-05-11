"""Equipment blueprint.

Owns the installed-base entities: ``Equipment``, ``EquipmentModel``,
``EquipmentControllerType``, ``EquipmentWarranty``. Mounted under
``/equipment``. Same thin-routes / services-own-the-ORM split as the
``clients`` blueprint.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "equipment",
    __name__,
    url_prefix="/equipment",
    template_folder="../templates/equipment",
)

from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
