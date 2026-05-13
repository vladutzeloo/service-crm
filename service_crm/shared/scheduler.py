"""APScheduler bootstrap — ROADMAP 0.7.0.

In-process :class:`BackgroundScheduler` that owns the recurring jobs
declared by the maintenance + planning + idempotency-sweep slices. The
scheduler stays in-process per
[`docs/architecture-plan.md`](../../docs/architecture-plan.md) §2.4
("Single-tenant deployment. One business per deployment.") — RQ +
Redis are post-1.0.

Gated on the ``SCHEDULER_ENABLED`` config flag so tests and dev don't
pay for background threads they don't want.
"""

from __future__ import annotations

import logging
from typing import Any

from apscheduler.schedulers.background import BackgroundScheduler
from flask import Flask, current_app

from ..extensions import db
from . import clock, idempotency

_LOG = logging.getLogger(__name__)

# Module-level singleton so ``init_app`` is idempotent — calling
# ``create_app`` twice in the same process (tests do it once for the
# session-scoped fixture, dev sometimes does it via the reloader) must
# not start two schedulers.
_SCHEDULER: BackgroundScheduler | None = None


def init_app(app: Flask) -> BackgroundScheduler | None:
    """Start the scheduler if the app config asks for it.

    Returns the active :class:`BackgroundScheduler` (or ``None`` when
    disabled). The instance is also stashed on
    ``app.extensions["scheduler"]`` for tests that want to introspect it.
    """
    if not app.config.get("SCHEDULER_ENABLED", False):
        app.extensions["scheduler"] = None
        return None
    global _SCHEDULER  # noqa: PLW0603 - module-level singleton, intentional
    if _SCHEDULER is not None and _SCHEDULER.running:
        app.extensions["scheduler"] = _SCHEDULER
        return _SCHEDULER
    scheduler = BackgroundScheduler(timezone="UTC")
    _register_jobs(scheduler, app)
    scheduler.start()
    _SCHEDULER = scheduler
    app.extensions["scheduler"] = scheduler
    _LOG.info("Background scheduler started with %d jobs", len(scheduler.get_jobs()))
    return scheduler


def _register_jobs(scheduler: BackgroundScheduler, app: Flask) -> None:
    maintenance_minutes = int(app.config.get("SCHEDULER_MAINTENANCE_INTERVAL_MIN", 60))
    idempotency_hours = int(app.config.get("SCHEDULER_IDEMPOTENCY_INTERVAL_H", 6))

    scheduler.add_job(
        _maintenance_tick_job,
        "interval",
        minutes=maintenance_minutes,
        id="maintenance_tick",
        kwargs={"app": app},
        replace_existing=True,
        next_run_time=clock.now(),
    )
    scheduler.add_job(
        _idempotency_sweep_job,
        "interval",
        hours=idempotency_hours,
        id="idempotency_sweep",
        kwargs={"app": app},
        replace_existing=True,
    )


def _maintenance_tick_job(*, app: Flask) -> dict[str, Any]:
    """Recompute every active maintenance plan and generate pending tasks."""
    # Lazy import to dodge the maintenance ↔ shared ↔ extensions chain at
    # module load time.
    from ..maintenance.services import scheduler_tick

    with app.app_context():
        try:
            stats = scheduler_tick(db.session)
            db.session.commit()
        except Exception:  # pragma: no cover - defensive: log and continue
            _LOG.exception("maintenance_tick failed")
            db.session.rollback()
            return {"error": True}
    _LOG.info(
        "maintenance_tick: %s plans recomputed, %s tasks generated",
        stats["plans_recomputed"],
        stats["tasks_generated"],
    )
    return stats


def _idempotency_sweep_job(*, app: Flask) -> int:
    with app.app_context():
        try:
            removed = idempotency.sweep(db.session)
            db.session.commit()
        except Exception:  # pragma: no cover - defensive
            _LOG.exception("idempotency_sweep failed")
            db.session.rollback()
            return -1
    _LOG.info("idempotency_sweep: %s rows removed", removed)
    return removed


def shutdown() -> None:
    """Stop the scheduler if it's running. Called by tests for cleanup."""
    global _SCHEDULER  # noqa: PLW0603 - module-level singleton
    if (
        _SCHEDULER is not None and _SCHEDULER.running
    ):  # pragma: no cover - covered when scheduler is enabled end-to-end
        _SCHEDULER.shutdown(wait=False)
    _SCHEDULER = None


def get_scheduler() -> BackgroundScheduler | None:
    """Lookup helper for callers outside the request lifecycle."""
    if _SCHEDULER is not None:  # pragma: no cover - covered only when SCHEDULER_ENABLED at app boot
        return _SCHEDULER
    try:
        from_app = current_app.extensions.get("scheduler")
    except RuntimeError:  # pragma: no cover - no app context
        return None
    return from_app if isinstance(from_app, BackgroundScheduler) else None


__all__ = ["get_scheduler", "init_app", "shutdown"]
