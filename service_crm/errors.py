"""Centralised error handlers.

We register handlers here so the factory stays uncluttered. Templates
land in 0.2.0 once the UI shell is vendored; for now we return JSON.
"""

from __future__ import annotations

from flask import Flask, jsonify
from flask.wrappers import Response
from werkzeug.exceptions import HTTPException


def register(app: Flask) -> None:
    app.register_error_handler(404, _not_found)
    app.register_error_handler(500, _server_error)
    app.register_error_handler(HTTPException, _http_exception)


def _not_found(_: Exception) -> tuple[Response, int]:
    return jsonify({"error": "not_found"}), 404


def _server_error(_: Exception) -> tuple[Response, int]:
    return jsonify({"error": "server_error"}), 500


def _http_exception(error: HTTPException) -> tuple[Response, int]:
    return jsonify({"error": error.name, "description": error.description}), (error.code or 500)
