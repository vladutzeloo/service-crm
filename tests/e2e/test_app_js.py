"""Static audit of ``static/js/app.js``.

We don't run JS in CI yet, but a handful of behaviours are part of the
foundation's contract and need to be locked in here so they don't get
silently dropped:

- the service-worker registration must pass the app version as ``?v=``
  so service-worker.js can derive a versioned cache key;
- the SW URL must read ``data-version`` from the ``.app`` element (set
  by base.html), not hardcode a value;
- there must be a modal-close handler so ``[data-modal-close="<id>"]``
  on the modal macro's close button actually closes the dialog.
"""

from __future__ import annotations

from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

APP_JS = Path(__file__).resolve().parents[2] / "service_crm" / "static" / "js" / "app.js"


@pytest.fixture(scope="module")
def app_js() -> str:
    return APP_JS.read_text(encoding="utf-8")


def test_service_worker_registration_includes_version(app_js: str) -> None:
    assert "/static/service-worker.js?v=" in app_js


def test_service_worker_reads_data_version_from_app(app_js: str) -> None:
    assert 'querySelector(".app")' in app_js
    assert 'getAttribute("data-version")' in app_js


def test_modal_close_handler_is_wired(app_js: str) -> None:
    assert "data-modal-close" in app_js
    assert "wireModals" in app_js
