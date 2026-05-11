"""Tests for the locale selector and the i18n smoke path."""

from __future__ import annotations

from typing import Any

import pytest
from flask import Flask

from service_crm.i18n import DEFAULT_LOCALE, SUPPORTED_LOCALES, select_locale


@pytest.mark.unit
def test_supported_locales_documented() -> None:
    assert "ro" in SUPPORTED_LOCALES
    assert "en" in SUPPORTED_LOCALES
    assert DEFAULT_LOCALE == "ro"


@pytest.mark.unit
def test_query_param_ro(app: Flask) -> None:
    with app.test_request_context("/?lang=ro"):
        assert select_locale() == "ro"


@pytest.mark.unit
def test_query_param_en(app: Flask) -> None:
    with app.test_request_context("/?lang=en"):
        assert select_locale() == "en"


@pytest.mark.unit
def test_query_param_unknown_falls_through(app: Flask) -> None:
    with app.test_request_context("/?lang=fr"):
        # 'fr' isn't supported → Accept-Language header → default 'ro'.
        assert select_locale() == "ro"


@pytest.mark.unit
def test_accept_language_header_en(app: Flask) -> None:
    with app.test_request_context("/", headers={"Accept-Language": "en-US,en;q=0.9"}):
        assert select_locale() == "en"


@pytest.mark.unit
def test_default_is_ro(app: Flask) -> None:
    with app.test_request_context("/"):
        assert select_locale() == "ro"


@pytest.mark.unit
def test_authenticated_user_pref_beats_query_string(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """User-level ``preferred_language`` takes precedence over ``?lang=``."""

    class _FakeUser:
        is_authenticated = True
        preferred_language = "en"

    monkeypatch.setattr("service_crm.i18n.current_user", _FakeUser())
    with app.test_request_context("/?lang=ro"):
        assert select_locale() == "en"


@pytest.mark.unit
def test_authenticated_user_with_unsupported_pref_falls_through(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    class _FakeUser:
        is_authenticated = True
        preferred_language = "de"

    monkeypatch.setattr("service_crm.i18n.current_user", _FakeUser())
    with app.test_request_context("/?lang=en"):
        # 'de' rejected → query says 'en' → return 'en'.
        assert select_locale() == "en"


@pytest.mark.unit
def test_anonymous_user_uses_query_string(app: Flask, monkeypatch: pytest.MonkeyPatch) -> None:
    class _AnonUser:
        is_authenticated = False
        preferred_language: Any = None

    monkeypatch.setattr("service_crm.i18n.current_user", _AnonUser())
    with app.test_request_context("/?lang=ro"):
        assert select_locale() == "ro"


@pytest.mark.unit
def test_configured_default_locale_wins_when_everything_else_falls_through(
    app: Flask, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The ``BABEL_DEFAULT_LOCALE`` config trumps the module constant when
    nothing else matches."""
    monkeypatch.setitem(app.config, "BABEL_DEFAULT_LOCALE", "en")
    # Force an Accept-Language we don't support so the header step also
    # falls through.
    with app.test_request_context("/", headers={"Accept-Language": "fr-FR"}):
        assert select_locale() == "en"
