"""Healthcheck and version blueprint.

``/healthz`` is for liveness probes; it does not touch the database.
``/version`` returns the value baked into ``app.config["VERSION"]`` at
factory time (read once from the ``VERSION`` file).

Both endpoints return a translated ``message`` field. They honour the
locale selector: ``/healthz?lang=ro`` and ``/healthz?lang=en`` differ.
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.wrappers import Response
from flask_babel import gettext as _

bp = Blueprint("health", __name__)


@bp.route("/healthz")
def healthz() -> Response:
    return jsonify({"status": "ok", "message": _("Service is healthy.")})


@bp.route("/version")
def version() -> Response:
    return jsonify({"version": current_app.config["VERSION"], "message": _("Service version.")})
