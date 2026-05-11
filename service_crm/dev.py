"""Developer-only blueprint.

Owns ``/dev/macro-smoke`` — the visual smoke page that renders every
shared macro with placeholder data, used to validate the 0.2.0 UI
foundation. The blueprint is mounted only when ``DEBUG`` or ``TESTING``
is true, so production builds never expose it. See
``docs/v1-implementation-goals.md`` §4.0.2.
"""

from __future__ import annotations

import uuid
from typing import Final

from flask import Blueprint, Flask, render_template

bp: Final[Blueprint] = Blueprint(
    "dev",
    __name__,
    url_prefix="/dev",
    template_folder="templates/dev",
)


@bp.route("/macro-smoke")
def macro_smoke() -> str:
    """Render every shared macro side-by-side.

    Reproducible placeholder data — the page is also the fixture for
    ``tests/e2e/test_macro_smoke.py``, which asserts each anchor element
    is present.
    """
    return render_template(
        "dev/macro_smoke.html",
        idempotency_token=uuid.uuid4().hex,
    )


def register(app: Flask) -> None:
    """Register the dev blueprint when the app is in DEBUG or TESTING mode."""
    if app.config.get("DEBUG") or app.config.get("TESTING"):
        app.register_blueprint(bp)
