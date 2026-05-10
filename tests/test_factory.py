"""Smoke tests for the application factory."""

from __future__ import annotations

import pytest
from flask import Flask

from service_crm import create_app
from service_crm.config import DevConfig, ProdConfig, TestConfig


@pytest.mark.unit
def test_create_app_dev() -> None:
    app = create_app(DevConfig)
    assert isinstance(app, Flask)
    assert app.config["DEBUG"] is True
    assert app.config["TESTING"] is False


@pytest.mark.unit
def test_create_app_test() -> None:
    app = create_app(TestConfig)
    assert app.config["TESTING"] is True
    assert app.config["WTF_CSRF_ENABLED"] is False


@pytest.mark.unit
def test_create_app_reads_version() -> None:
    app = create_app(TestConfig)
    version = app.config["VERSION"]
    assert isinstance(version, str)
    assert version  # non-empty


@pytest.mark.unit
def test_prod_config_validate_rejects_default_secret() -> None:
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        ProdConfig.validate()
