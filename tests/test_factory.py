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


@pytest.mark.unit
def test_read_version_falls_back_when_file_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: object
) -> None:
    """If the ``VERSION`` file is missing, the factory should still boot
    with a placeholder. This covers the ``FileNotFoundError`` branch in
    ``_read_version_file``."""
    from pathlib import Path

    import service_crm

    real_resolve = Path.resolve

    def _fake_resolve(self: Path, *args: object, **kwargs: object) -> Path:
        # Redirect only the call from ``_read_version_file`` to an empty
        # directory; everything else keeps its real behaviour.
        if self.name == "__init__.py" and "service_crm" in str(self):
            return Path("/tmp/definitely-not-a-real-service-crm-dir/__init__.py")
        return real_resolve(self, *args, **kwargs)  # type: ignore[arg-type]

    monkeypatch.setattr(Path, "resolve", _fake_resolve)
    assert service_crm._read_version_file() == "0.0.0"
