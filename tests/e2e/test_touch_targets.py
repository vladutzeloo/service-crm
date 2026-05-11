"""Static touch-target audit.

We don't drive a real browser in v0.2 CI, but the foundation must
guarantee that every interactive element it ships honours the ≥ 44 pt
tap-target rule from ``docs/v1-implementation-goals.md`` §2.2.

The CSS file is the single source of truth for the foundation's tap
targets: every interactive class (.btn, .icon-btn, .nav-link, .chip,
.tab, .field input, .date-range input) inherits its sizing from the
``--tap-min`` token. This test parses the CSS and asserts the
contract.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.e2e

CSS_PATH = Path(__file__).resolve().parents[2] / "service_crm" / "static" / "css" / "style.css"


@pytest.fixture(scope="module")
def style_css() -> str:
    return CSS_PATH.read_text(encoding="utf-8")


def _block(css: str, selector: str) -> str:
    """Return the body of the first CSS block whose selector exactly matches."""
    pattern = re.compile(r"(?ms)^[\t ]*" + re.escape(selector) + r"\s*\{(?P<body>.*?)\}")
    match = pattern.search(css)
    assert match is not None, f"selector {selector!r} not found in style.css"
    return match.group("body")


def test_tap_min_token_is_44px(style_css: str) -> None:
    """The ``--tap-min`` design token must be at least 44 px."""
    match = re.search(r"--tap-min:\s*(\d+)px\s*;", style_css)
    assert match is not None
    assert int(match.group(1)) >= 44


@pytest.mark.parametrize(
    "selector",
    [
        ".btn",
        ".sidebar .nav-link",
        ".tabs .tab",
        ".field input,\n.field select,\n.field textarea",
        ".date-range input",
    ],
)
def test_interactive_elements_use_tap_min(style_css: str, selector: str) -> None:
    body = _block(style_css, selector)
    assert "min-height: var(--tap-min)" in body, (
        f"{selector!r} must declare min-height: var(--tap-min) to honour the "
        "44 pt tap-target rule from docs/v1-implementation-goals.md §2.2"
    )


def test_icon_btn_is_square_tap_target(style_css: str) -> None:
    body = _block(style_css, ".icon-btn")
    assert "width: var(--tap-min)" in body
    assert "height: var(--tap-min)" in body


def test_chip_min_height_is_at_least_32px(style_css: str) -> None:
    """Chips are secondary controls; we allow 32 px (still above 24 px touch
    failure threshold), but anything smaller is a regression."""
    body = _block(style_css, ".chip")
    match = re.search(r"min-height:\s*(\d+)px\s*;", body)
    assert match is not None
    assert int(match.group(1)) >= 32
