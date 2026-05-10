"""Tests for service_crm.config helpers and class behaviour."""

from __future__ import annotations

import pytest

from service_crm import config
from service_crm.config import BaseConfig, ProdConfig


@pytest.mark.unit
@pytest.mark.parametrize(
    "raw, expected",
    [
        ("1", True),
        ("true", True),
        ("YES", True),
        (" on ", True),
        ("0", False),
        ("false", False),
        ("nope", False),
        ("", False),
    ],
)
def test_bool_helper_parses_truthy_strings(
    monkeypatch: pytest.MonkeyPatch, raw: str, expected: bool
) -> None:
    monkeypatch.setenv("SVC_CRM_TEST_BOOL", raw)
    assert config._bool("SVC_CRM_TEST_BOOL", default=not expected) is expected


@pytest.mark.unit
def test_bool_helper_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SVC_CRM_TEST_BOOL", raising=False)
    assert config._bool("SVC_CRM_TEST_BOOL", default=True) is True
    assert config._bool("SVC_CRM_TEST_BOOL", default=False) is False


@pytest.mark.unit
def test_int_helper_parses_set_value(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SVC_CRM_TEST_INT", "42")
    assert config._int("SVC_CRM_TEST_INT", default=0) == 42


@pytest.mark.unit
def test_int_helper_returns_default_when_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("SVC_CRM_TEST_INT", raising=False)
    assert config._int("SVC_CRM_TEST_INT", default=99) == 99


@pytest.mark.unit
def test_prod_config_validate_accepts_custom_secret() -> None:
    """The happy path: a SECRET_KEY that isn't the dev default should pass."""

    class _Prod(ProdConfig):
        SECRET_KEY = "not-the-default"

    # Should not raise; returning None is the success contract.
    assert _Prod.validate() is None


@pytest.mark.unit
def test_base_config_secret_key_default_is_documented_dev_placeholder() -> None:
    """The default ``SECRET_KEY`` is intentionally insecure; ``ProdConfig.validate``
    rejects it. This test pins the constant so a silent change is caught."""
    assert BaseConfig.SECRET_KEY == "dev-secret-do-not-use-in-prod"
