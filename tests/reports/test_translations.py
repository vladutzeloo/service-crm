"""Translation registry smoke tests for the reports blueprint."""

from __future__ import annotations

from service_crm.reports._translations import (
    PERIOD_LABELS,
    REPORT_CODES,
    REPORT_DESCRIPTIONS,
    REPORT_LABELS,
    period_label,
    report_description,
    report_label,
)


def test_report_codes_match_v1_blueprint_section_14() -> None:
    """Six reports per docs/blueprint.md §14."""
    assert set(REPORT_CODES) == {
        "tickets_by_status",
        "interventions_by_machine",
        "parts_used",
        "maintenance_due_vs_completed",
        "technician_workload",
        "repeat_issues",
    }
    # Order is stable for the index template.
    assert len(REPORT_CODES) == 6


def test_report_labels_cover_every_code() -> None:
    assert set(REPORT_LABELS) == set(REPORT_CODES)


def test_report_descriptions_cover_every_code() -> None:
    assert set(REPORT_DESCRIPTIONS) == set(REPORT_CODES)


def test_period_labels_cover_three_buckets() -> None:
    assert set(PERIOD_LABELS) == {"day", "week", "month"}


def test_report_label_falls_back_to_code() -> None:
    assert report_label("unknown") == "unknown"


def test_report_description_falls_back_to_empty() -> None:
    assert report_description("unknown") == ""


def test_period_label_falls_back_to_code() -> None:
    assert period_label("unknown") == "unknown"
