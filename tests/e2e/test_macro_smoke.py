"""End-to-end smoke tests for the 0.2.0 UI foundation.

Each test hits ``/dev/macro-smoke`` and asserts the anchor element the
corresponding macro emits. No screenshot diffing — the goal is to
verify that the macros render at all and produce the expected DOM
attributes that follow-on slices and consistency passes rely on.
"""

from __future__ import annotations

import pytest
from flask.testing import FlaskClient

pytestmark = pytest.mark.e2e


def _get_smoke(client: FlaskClient) -> str:
    response = client.get("/dev/macro-smoke")
    assert response.status_code == 200
    return response.get_data(as_text=True)


def test_base_shell_is_rendered(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert '<aside class="sidebar"' in body
    assert '<header class="topbar"' in body
    assert 'class="main"' in body
    assert "data-theme-toggle" in body
    assert "data-nav-toggle" in body
    # The app version is exposed to JS so the service-worker registration
    # can derive its cache key (see js/app.js::registerServiceWorker).
    assert "data-version=" in body


def test_language_switch_preserves_query_args(client: FlaskClient) -> None:
    """Switching language must not drop existing ``?`` parameters
    (search, filters, pagination)."""
    response = client.get("/dev/macro-smoke?search=foo&page=3")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    # The lang switch renders a GET form, not bare anchors with ?lang=.
    assert 'name="lang" value="ro"' in body
    assert 'name="lang" value="en"' in body
    # Other args round-trip as hidden inputs.
    assert 'type="hidden" name="search" value="foo"' in body
    assert 'type="hidden" name="page" value="3"' in body
    # The literal ``?lang=ro`` href that used to drop siblings is gone.
    assert 'href="?lang=ro"' not in body
    assert 'href="?lang=en"' not in body


def test_pwa_links_are_present(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert "manifest.webmanifest" in body
    assert "apple-touch-icon" in body
    assert "css/style.css" in body
    assert "js/app.js" in body


def test_kpi_card_macro_renders_anchor(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert body.count('class="oee-card accent-top"') >= 4


def test_data_table_macro_renders_anchor(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert 'class="data-table table-stacked"' in body
    assert "<thead>" in body
    assert "<tbody>" in body
    assert 'data-label="' in body  # stacked-card label hook on every cell


def test_filter_bar_macro_renders_anchor(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert '<section class="filter-bar"' in body
    assert 'class="chip is-active"' in body
    assert 'type="date"' in body


def test_filter_bar_date_range_can_be_submitted(client: FlaskClient) -> None:
    """When ``action`` is supplied the date-range must render as a real
    GET form with an Apply submit button — without it the user has no
    way to commit a date change."""
    body = _get_smoke(client)
    assert '<form method="get" action="/dev/macro-smoke" class="date-range">' in body
    assert 'name="from"' in body
    assert 'name="to"' in body
    assert 'type="submit"' in body


def test_form_shell_macro_carries_idempotency_token(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert 'class="form-shell"' in body
    assert 'name="idempotency_token"' in body
    # WTForms isn't involved here so no CSRF token is rendered by the macro
    # itself; auth-blueprint forms pass form.csrf_token in 0.3.0+.


def test_tabs_macro_renders_anchor(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert '<nav class="tabs"' in body
    assert 'class="tab is-active"' in body
    assert 'aria-current="page"' in body


def test_modal_macro_renders_anchor(client: FlaskClient) -> None:
    body = _get_smoke(client)
    assert 'role="dialog"' in body
    assert 'aria-modal="true"' in body
    assert 'class="modal-card"' in body


def test_manifest_is_served(client: FlaskClient) -> None:
    response = client.get("/static/manifest.webmanifest")
    assert response.status_code == 200
    payload = response.get_data(as_text=True)
    assert '"start_url": "/"' in payload
    assert '"display": "standalone"' in payload
    # Manifest must list at least one 192, one 512, and one maskable icon.
    assert '"sizes": "192x192"' in payload
    assert '"sizes": "512x512"' in payload
    assert '"purpose": "maskable"' in payload


def test_service_worker_is_served(client: FlaskClient) -> None:
    response = client.get("/static/service-worker.js")
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert "CACHE_NAME" in body
    assert "SKIP_WAITING" in body
    # No write-side caching in v1 — assert the worker passes non-GET through.
    assert 'req.method !== "GET"' in body


def test_icons_are_served(client: FlaskClient) -> None:
    for name in ("icon.svg", "icon-192.png", "icon-512.png", "icon-maskable-512.png"):
        response = client.get(f"/static/icons/{name}")
        assert response.status_code == 200, name


def test_smoke_page_unavailable_when_not_debug_or_testing() -> None:
    """``dev.register`` only mounts the blueprint in DEBUG or TESTING."""
    from service_crm import create_app
    from service_crm.config import BaseConfig

    class FrozenConfig(BaseConfig):
        TESTING = False
        DEBUG = False

    prod_like = create_app(FrozenConfig)
    with prod_like.test_client() as c:
        response = c.get("/dev/macro-smoke")
    assert response.status_code == 404
