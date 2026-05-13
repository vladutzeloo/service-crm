"""Coverage tests for the intervention translation helper."""

from __future__ import annotations

import pytest

from service_crm.tickets._intervention_translations import (
    FINDING_KIND_LABELS,
    finding_kind_label,
)


@pytest.mark.unit
def test_finding_kind_labels_present() -> None:
    assert set(FINDING_KIND_LABELS) == {"observation", "root_cause"}


@pytest.mark.unit
def test_finding_kind_label_falls_back_to_code() -> None:
    # Outside a request context the lazy_gettext str() returns the raw
    # English label. Both branches of the bool flag run through; just
    # check the call doesn't raise and returns a string.
    assert isinstance(finding_kind_label(True), str)
    assert isinstance(finding_kind_label(False), str)
