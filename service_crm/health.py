"""Healthcheck and version blueprint.

``/healthz`` is for liveness probes; it does not touch the database.
``/version`` returns the value baked into ``app.config["VERSION"]`` at
factory time (read once from the ``VERSION`` file).
"""

from __future__ import annotations

from flask import Blueprint, current_app, jsonify
from flask.wrappers import Response

bp = Blueprint("health", __name__)


@bp.route("/healthz")
def healthz() -> Response:
    return jsonify({"status": "ok"})


@bp.route("/version")
def version() -> Response:
    return jsonify({"version": current_app.config["VERSION"]})
