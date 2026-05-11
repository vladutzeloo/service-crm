"""Clients blueprint.

Owns Client, Contact, Location, and ServiceContract models plus all
CRUD routes. Registered under the ``/clients`` URL prefix.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "clients",
    __name__,
    url_prefix="/clients",
    template_folder="../templates/clients",
)

# Importing models + routes at registration time wires SQLAlchemy metadata
# and registers URL rules in one step (same pattern as the auth blueprint).
from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
