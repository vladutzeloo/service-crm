"""Tests for the dev-only blueprint registration logic.

The dev blueprint owns ``/dev/macro-smoke``; it must only mount when
``DEBUG`` or ``TESTING`` is true, so production builds never expose it
even by accident.
"""

from __future__ import annotations

import pytest
from flask import Flask

from service_crm import create_app
from service_crm.config import BaseConfig, DevConfig, TestConfig

pytestmark = pytest.mark.e2e


class _ProdLikeConfig(BaseConfig):
    DEBUG = False
    TESTING = False


def _app(config: type[BaseConfig]) -> Flask:
    return create_app(config)


def test_dev_blueprint_mounted_under_testing() -> None:
    app = _app(TestConfig)
    assert "dev" in app.blueprints


def test_dev_blueprint_mounted_under_debug() -> None:
    app = _app(DevConfig)
    assert "dev" in app.blueprints


def test_dev_blueprint_skipped_in_prod_like_config() -> None:
    app = _app(_ProdLikeConfig)
    assert "dev" not in app.blueprints
    with app.test_client() as client:
        assert client.get("/dev/macro-smoke").status_code == 404
