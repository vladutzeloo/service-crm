"""Auth blueprint.

Owns ``User`` and ``Role``. Routes / forms / templates land with
``/module-slice auth`` in the next PR; this package is for the model
layer and password helpers only.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint("auth", __name__, url_prefix="/auth")

# Importing the models module here registers them with the SQLAlchemy
# metadata at blueprint-registration time, so Alembic autogenerate and
# `db.create_all` both see them.
from . import models  # noqa: E402, F401
