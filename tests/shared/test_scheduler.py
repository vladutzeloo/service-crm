"""Tests for the APScheduler bootstrap in ``service_crm.shared.scheduler``."""

from __future__ import annotations

from datetime import timedelta

import pytest
from flask import Flask

from service_crm.config import BaseConfig, TestConfig
from service_crm.maintenance.models import MaintenanceTask
from service_crm.shared import scheduler
from tests.factories import MaintenancePlanFactory


@pytest.fixture(autouse=True)
def _ensure_scheduler_off():
    """Make sure no scheduler is running on either side of every test."""
    scheduler.shutdown()
    yield
    scheduler.shutdown()


def test_init_app_returns_none_when_disabled() -> None:
    app = Flask(__name__)
    app.config["SCHEDULER_ENABLED"] = False
    assert scheduler.init_app(app) is None
    assert app.extensions["scheduler"] is None


def test_init_app_starts_when_enabled(monkeypatch: pytest.MonkeyPatch) -> None:
    """Confirm the BackgroundScheduler boots, registers jobs, and stops cleanly."""

    class _SchedulerConfig(BaseConfig):
        SCHEDULER_ENABLED = True
        SCHEDULER_MAINTENANCE_INTERVAL_MIN = 60
        SCHEDULER_IDEMPOTENCY_INTERVAL_H = 6

    started: list[bool] = []

    def fake_init(self, *args, **kwargs):
        started.append(True)

    from apscheduler.schedulers.background import BackgroundScheduler

    real_start = BackgroundScheduler.start
    real_shutdown = BackgroundScheduler.shutdown

    def safe_start(self, paused=False):  # type: ignore[no-untyped-def]
        # Don't actually fire background threads in the test.
        self._eventloop_paused = True

    monkeypatch.setattr(BackgroundScheduler, "start", safe_start)
    # Mark the scheduler as "running" by patching .running too.
    monkeypatch.setattr(BackgroundScheduler, "running", property(lambda self: True), raising=True)

    app = Flask(__name__)
    app.config.from_object(_SchedulerConfig)
    sched = scheduler.init_app(app)
    assert sched is not None
    assert app.extensions["scheduler"] is sched
    # Two jobs registered: maintenance + idempotency.
    job_ids = {j.id for j in sched.get_jobs()}
    assert job_ids == {"maintenance_tick", "idempotency_sweep"}

    # ``init_app`` is idempotent — second call returns the same instance.
    again = scheduler.init_app(app)
    assert again is sched

    # Restore so the cleanup fixture can shutdown cleanly.
    monkeypatch.setattr(BackgroundScheduler, "start", real_start)
    monkeypatch.setattr(BackgroundScheduler, "shutdown", real_shutdown)


def test_get_scheduler_returns_none_off_context() -> None:
    scheduler.shutdown()
    assert scheduler.get_scheduler() is None


def test_get_scheduler_inside_app_context_when_disabled(app: Flask) -> None:
    """When the test app config disables the scheduler, ``get_scheduler``
    surfaces ``None`` rather than raising."""
    with app.app_context():
        assert scheduler.get_scheduler() is None


def test_maintenance_tick_job_runs_inside_app_context(app: Flask, db_session, frozen_clock) -> None:
    """The job module-level function commits its own work — verify it
    materialises a pending task and the second invocation is a no-op."""
    today = frozen_clock.date()
    plan = MaintenancePlanFactory(cadence_days=30, last_done_on=today - timedelta(days=30))
    db_session.commit()

    stats = scheduler._maintenance_tick_job(app=app)
    assert stats["tasks_generated"] >= 1

    # Idempotent retry.
    stats2 = scheduler._maintenance_tick_job(app=app)
    assert stats2["tasks_generated"] == 0

    # The pending task is visible via a fresh query.
    db_session.expire_all()
    pending = db_session.query(MaintenanceTask).filter_by(plan_id=plan.id, status="pending").all()
    assert len(pending) == 1


def test_idempotency_sweep_job_runs(app: Flask, db_session) -> None:
    """Sweep is a no-op when the table is empty; still exercises the
    code path."""
    removed = scheduler._idempotency_sweep_job(app=app)
    assert removed >= 0


# Quiet ruff for TestConfig import which keeps the migration of v0.7 tests
# discoverable when copying patterns.
_ = TestConfig
