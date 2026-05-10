"""Tests for the Auditable mixin contract.

The full ``before_flush`` listener is exercised end-to-end in the auth
data-model PR, where ``users`` and ``roles`` tables actually exist. Here
we just verify the mixin shape and the context-var plumbing.
"""

from __future__ import annotations

import pytest

from service_crm.shared.audit import (
    ACTOR_CTX,
    REQUEST_ID_CTX,
    Auditable,
    AuditEvent,
)


@pytest.mark.unit
def test_auditable_declares_timestamp_columns() -> None:
    assert "created_at" in dir(Auditable)
    assert "updated_at" in dir(Auditable)


@pytest.mark.unit
def test_audit_event_columns() -> None:
    table = AuditEvent.__table__
    expected = {
        "id",
        "ts",
        "action",
        "entity_type",
        "entity_id",
        "actor_user_id",
        "request_id",
        "before",
        "after",
    }
    assert expected <= {col.name for col in table.columns}


@pytest.mark.unit
def test_actor_ctx_default_is_none() -> None:
    assert ACTOR_CTX.get() is None
    assert REQUEST_ID_CTX.get() is None


@pytest.mark.unit
def test_actor_ctx_round_trip() -> None:
    token = ACTOR_CTX.set(b"\x00" * 16)
    try:
        assert ACTOR_CTX.get() == b"\x00" * 16
    finally:
        ACTOR_CTX.reset(token)
    assert ACTOR_CTX.get() is None


# --- listener body ----------------------------------------------------------
# We don't have ``users`` / ``roles`` tables yet, so we exercise the
# listener against a fake session where ``new``/``dirty``/``deleted`` are
# plain sets. The full DB-backed path lights up in /data-model.


class _FakeSession:
    def __init__(
        self,
        new: set[object] | None = None,
        dirty: set[object] | None = None,
        deleted: set[object] | None = None,
    ) -> None:
        self.new = new or set()
        self.dirty = dirty or set()
        self.deleted = deleted or set()
        self.added: list[object] = []

    def is_modified(self, _instance: object, **_kwargs: object) -> bool:
        return True

    def add(self, instance: object) -> None:
        self.added.append(instance)


class _FakeAuditable(Auditable):
    """Minimal Auditable subclass that doesn't touch SQLAlchemy."""

    def __init__(self, name: str) -> None:
        self.id = b"\x01" * 16
        self.name = name


def _patch_inspect(monkeypatch: pytest.MonkeyPatch) -> None:
    """Stub out sqlalchemy.inspect so we don't need a real mapper."""

    class _Attr:
        def __init__(self, key: str, value: object) -> None:
            self.key = key
            self.loaded_value = value

    class _State:
        def __init__(self, instance: object) -> None:
            self.attrs = [
                _Attr("id", getattr(instance, "id", None)),
                _Attr("name", getattr(instance, "name", None)),
            ]

    monkeypatch.setattr("service_crm.shared.audit.inspect", _State)


@pytest.mark.unit
def test_listener_skips_when_no_app_context(monkeypatch: pytest.MonkeyPatch) -> None:
    from service_crm.shared.audit import _record_audit_events

    monkeypatch.setattr("service_crm.shared.audit.has_app_context", lambda: False)
    session = _FakeSession(new={_FakeAuditable("a")})
    _record_audit_events(session, None, None)  # type: ignore[arg-type]
    assert session.added == []


@pytest.mark.unit
def test_listener_emits_create_update_delete_events(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from service_crm.shared.audit import _record_audit_events

    monkeypatch.setattr("service_crm.shared.audit.has_app_context", lambda: True)

    class _App:
        def __init__(self) -> None:
            self.config: dict[str, object] = {"AUDIT_LOG_ENABLED": True}

    monkeypatch.setattr("service_crm.shared.audit.current_app", _App())
    _patch_inspect(monkeypatch)

    created = _FakeAuditable("created")
    updated = _FakeAuditable("updated")
    deleted = _FakeAuditable("deleted")
    session = _FakeSession(new={created}, dirty={updated}, deleted={deleted})

    _record_audit_events(session, None, None)  # type: ignore[arg-type]

    actions = sorted(evt.action for evt in session.added)  # type: ignore[attr-defined]
    assert actions == ["create", "delete", "update"]
    # delete event has no `after` payload.
    delete_evt = next(evt for evt in session.added if evt.action == "delete")  # type: ignore[attr-defined]
    assert delete_evt.after is None  # type: ignore[attr-defined]


@pytest.mark.unit
def test_listener_respects_audit_disabled_flag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from service_crm.shared.audit import _record_audit_events

    monkeypatch.setattr("service_crm.shared.audit.has_app_context", lambda: True)

    class _App:
        def __init__(self) -> None:
            self.config: dict[str, object] = {"AUDIT_LOG_ENABLED": False}

    monkeypatch.setattr("service_crm.shared.audit.current_app", _App())
    session = _FakeSession(new={_FakeAuditable("x")})
    _record_audit_events(session, None, None)  # type: ignore[arg-type]
    assert session.added == []


@pytest.mark.unit
def test_coerce_handles_each_type() -> None:
    from datetime import UTC, datetime

    from service_crm.shared.audit import _coerce

    assert _coerce(None) is None
    assert _coerce(1) == 1
    assert _coerce("x") == "x"
    assert _coerce(True) is True
    assert _coerce(b"\x01\x02") == "0102"
    ts = datetime(2026, 5, 10, tzinfo=UTC)
    assert _coerce(ts) == ts.isoformat()
    # Anything else falls back to str()
    assert _coerce([1, 2]) == "[1, 2]"
