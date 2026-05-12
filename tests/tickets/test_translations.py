"""Tests for the small translation/tone registry."""

from __future__ import annotations

import pytest

from service_crm.tickets._translations import (
    PRIORITY_LABELS,
    PRIORITY_TONE,
    STATUS_LABELS,
    STATUS_TONE,
    TYPE_LABELS,
    priority_label,
    priority_tone,
    status_label,
    status_tone,
    type_label,
)


@pytest.mark.unit
def test_every_status_has_a_label_and_tone() -> None:
    expected_codes = {
        "new",
        "qualified",
        "scheduled",
        "in_progress",
        "waiting_parts",
        "monitoring",
        "completed",
        "closed",
        "cancelled",
    }
    assert set(STATUS_LABELS) >= expected_codes
    assert set(STATUS_TONE) >= expected_codes


@pytest.mark.unit
def test_priority_and_type_registry_includes_seeds() -> None:
    assert set(PRIORITY_LABELS) >= {"low", "normal", "high", "urgent"}
    assert set(TYPE_LABELS) >= {
        "incident",
        "preventive",
        "commissioning",
        "warranty",
        "installation",
        "audit",
    }
    assert PRIORITY_TONE["urgent"] == "first-off"


@pytest.mark.unit
def test_label_lookups_fall_back_to_code() -> None:
    """Unknown codes return the input untranslated.

    Outside of a request context the ``lazy_gettext`` proxies raise on
    ``str()`` conversion, but our helpers swallow that and return the
    raw code.
    """
    assert status_label("totally-unknown-status-code-12345") == (
        "totally-unknown-status-code-12345"
    )
    assert type_label("totally-unknown-type-code-12345") == ("totally-unknown-type-code-12345")
    assert priority_label("totally-unknown-prio-code-12345") == ("totally-unknown-prio-code-12345")


@pytest.mark.unit
def test_tone_lookups_fall_back_to_muted() -> None:
    assert status_tone("totally-unknown") == "muted"
    assert priority_tone("totally-unknown") == "muted"
