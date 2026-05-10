"""Tests for the /healthz and /version endpoints."""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient


@pytest.mark.e2e
def test_healthz_returns_ok(client: FlaskClient) -> None:
    response = client.get("/healthz")
    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


@pytest.mark.e2e
def test_version_returns_a_version_string(client: FlaskClient) -> None:
    response = client.get("/version")
    assert response.status_code == 200
    body = response.get_json()
    assert "version" in body
    assert isinstance(body["version"], str)
    assert body["version"]


@pytest.mark.e2e
def test_unknown_route_returns_json_404(client: FlaskClient) -> None:
    response = client.get("/does-not-exist")
    assert response.status_code == 404
    assert response.get_json() == {"error": "not_found"}


@pytest.mark.unit
def test_server_error_handler_returns_json() -> None:
    """A 500 inside any view should be caught by ``_server_error`` and
    serialized as JSON."""
    from flask import Flask

    from service_crm.config import TestConfig
    from service_crm.errors import register

    app = Flask(__name__)
    app.config.from_object(TestConfig)
    app.config["PROPAGATE_EXCEPTIONS"] = False
    register(app)

    @app.route("/boom")
    def _boom() -> str:
        raise RuntimeError("kaboom")

    client = app.test_client()
    response = client.get("/boom")
    assert response.status_code == 500
    assert response.get_json() == {"error": "server_error"}


@pytest.mark.unit
def test_http_exception_handler_serializes_arbitrary_exception() -> None:
    """A ``werkzeug.HTTPException`` raised explicitly (e.g. ``abort(418)``)
    should route through ``_http_exception``."""
    from flask import Flask, abort

    from service_crm.config import TestConfig
    from service_crm.errors import register

    app = Flask(__name__)
    app.config.from_object(TestConfig)
    register(app)

    @app.route("/teapot")
    def _teapot() -> str:
        abort(418, description="i am a teapot")
        return ""  # unreachable, satisfies type checker

    client = app.test_client()
    response = client.get("/teapot")
    assert response.status_code == 418
    body = response.get_json()
    assert body["error"].lower() == "i'm a teapot"
    assert body["description"] == "i am a teapot"
