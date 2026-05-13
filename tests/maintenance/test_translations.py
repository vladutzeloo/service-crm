"""Translation registry for the maintenance blueprint."""

from __future__ import annotations

import pytest
from flask import Flask

from service_crm.maintenance._translations import (
    TASK_STATUS_LABELS,
    task_status_label,
    task_status_tone,
)
from service_crm.maintenance.models import TaskStatus


def test_task_status_labels_cover_all_codes() -> None:
    assert set(TASK_STATUS_LABELS) == TaskStatus.ALL


@pytest.mark.parametrize("code", ["pending", "done", "escalated"])
def test_task_status_label_resolves(code: str, app: Flask) -> None:
    with app.test_request_context():
        assert task_status_label(code)


def test_task_status_label_unknown_passthrough() -> None:
    # Falls back to raw code when no translation present.
    assert task_status_label("bogus") == "bogus"


def test_task_status_tone_known() -> None:
    assert task_status_tone(TaskStatus.PENDING) == "warning"
    assert task_status_tone(TaskStatus.DONE) == "success"
    assert task_status_tone(TaskStatus.ESCALATED) == "info"


def test_task_status_tone_unknown_default() -> None:
    assert task_status_tone("bogus") == "default"
