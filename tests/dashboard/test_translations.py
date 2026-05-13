"""Translation registry smoke tests for the dashboard blueprint."""

from __future__ import annotations

from service_crm.dashboard._translations import (
    KPI_LABELS,
    PANEL_LABELS,
    kpi_label,
    panel_label,
)


def test_kpi_labels_cover_every_v1_tile() -> None:
    expected = {
        "active_clients",
        "open_tickets",
        "overdue_tickets",
        "due_maintenance_week",
        "tickets_waiting_parts",
        "technician_utilization",
    }
    assert set(KPI_LABELS) == expected


def test_panel_labels_cover_v1_panels() -> None:
    expected = {
        "tickets_by_status",
        "upcoming_maintenance",
        "recent_interventions",
        "high_risk_machines",
        "technician_load_week",
        "my_queue",
        "my_overdue",
        "my_maintenance",
    }
    assert set(PANEL_LABELS) == expected


def test_kpi_label_falls_back_to_code() -> None:
    assert kpi_label("unknown_code") == "unknown_code"


def test_panel_label_falls_back_to_code() -> None:
    assert panel_label("unknown_panel") == "unknown_panel"


def test_known_kpi_label_returns_translation_string() -> None:
    label = kpi_label("active_clients")
    # Default locale is English in tests.
    assert "client" in label.lower()
