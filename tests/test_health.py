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
