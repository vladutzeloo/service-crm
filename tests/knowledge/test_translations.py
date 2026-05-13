"""Coverage tests for knowledge translation helpers."""

from __future__ import annotations

import pytest

from service_crm.knowledge._translations import CHECKLIST_KIND_LABELS, kind_label


@pytest.mark.unit
def test_every_kind_has_a_label() -> None:
    assert set(CHECKLIST_KIND_LABELS) == {"bool", "text", "number", "choice"}


@pytest.mark.unit
def test_kind_label_falls_back_to_code() -> None:
    """Unknown kind returns the raw code (the lazy_gettext proxy raises
    outside a request context; helper swallows that and returns the
    fallback)."""
    assert kind_label("totally-unknown-kind-zzz") == "totally-unknown-kind-zzz"
