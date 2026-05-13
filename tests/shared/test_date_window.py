"""Tests for ``service_crm.shared.date_window``."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from service_crm.shared import date_window as dw


def test_date_window_properties() -> None:
    w = dw.DateWindow(start=date(2026, 5, 1), end_exclusive=date(2026, 5, 14))
    assert w.days == 13
    assert w.end_inclusive == date(2026, 5, 13)
    assert w.contains(date(2026, 5, 1))
    assert w.contains(date(2026, 5, 13))
    assert not w.contains(date(2026, 5, 14))
    assert not w.contains(date(2026, 4, 30))
    assert w.iso_label() == "20260501-20260513"


def test_this_week_anchors_to_monday() -> None:
    # Wednesday 2026-05-13 → Mon 2026-05-11 .. Mon 2026-05-18.
    w = dw.this_week(today=date(2026, 5, 13))
    assert w.start == date(2026, 5, 11)
    assert w.end_exclusive == date(2026, 5, 18)
    assert w.days == 7


def test_this_week_when_today_is_monday() -> None:
    w = dw.this_week(today=date(2026, 5, 11))
    assert w.start == date(2026, 5, 11)
    assert w.end_exclusive == date(2026, 5, 18)


def test_this_week_when_today_is_sunday() -> None:
    w = dw.this_week(today=date(2026, 5, 17))
    assert w.start == date(2026, 5, 11)
    assert w.end_exclusive == date(2026, 5, 18)


def test_this_month_mid_month() -> None:
    w = dw.this_month(today=date(2026, 5, 13))
    assert w.start == date(2026, 5, 1)
    assert w.end_exclusive == date(2026, 6, 1)
    assert w.days == 31


def test_this_month_december_rolls_over() -> None:
    w = dw.this_month(today=date(2026, 12, 15))
    assert w.start == date(2026, 12, 1)
    assert w.end_exclusive == date(2027, 1, 1)


def test_last_n_days_window() -> None:
    w = dw.last_n_days(7, today=date(2026, 5, 13))
    assert w.start == date(2026, 5, 7)
    assert w.end_exclusive == date(2026, 5, 14)
    assert w.days == 7


def test_last_n_days_rejects_non_positive() -> None:
    with pytest.raises(ValueError):
        dw.last_n_days(0)


class _FakeArgs:
    """Mimics Werkzeug's ImmutableMultiDict.get."""

    def __init__(self, **data: str) -> None:
        self._data = data

    def get(self, key: str) -> str | None:
        return self._data.get(key)


def test_parse_window_uses_default_when_missing() -> None:
    default = dw.DateWindow(start=date(2026, 1, 1), end_exclusive=date(2026, 1, 8))
    out = dw.parse_window(_FakeArgs(), default=default)
    assert out == default


def test_parse_window_uses_this_month_when_no_default() -> None:
    out = dw.parse_window(_FakeArgs(), today=date(2026, 5, 13))
    assert out.start == date(2026, 5, 1)
    assert out.end_exclusive == date(2026, 6, 1)


def test_parse_window_parses_from_and_to() -> None:
    args = _FakeArgs(**{"from": "2026-05-01", "to": "2026-05-13"})
    out = dw.parse_window(args)
    assert out.start == date(2026, 5, 1)
    assert out.end_exclusive == date(2026, 5, 14)  # half-open


def test_parse_window_swaps_inverted_inputs() -> None:
    args = _FakeArgs(**{"from": "2026-05-13", "to": "2026-05-01"})
    out = dw.parse_window(args)
    assert out.start == date(2026, 5, 1)
    assert out.end_exclusive == date(2026, 5, 14)


def test_parse_window_falls_back_on_malformed_dates() -> None:
    default = dw.DateWindow(start=date(2026, 1, 1), end_exclusive=date(2026, 1, 2))
    args = _FakeArgs(**{"from": "nope", "to": "also-nope"})
    out = dw.parse_window(args, default=default)
    assert out == default


def test_parse_window_falls_back_when_only_one_present() -> None:
    default = dw.DateWindow(start=date(2026, 1, 1), end_exclusive=date(2026, 1, 2))
    args = _FakeArgs(**{"from": "2026-05-01"})
    out = dw.parse_window(args, default=default)
    assert out == default


def test_parse_window_handles_args_without_get() -> None:
    """Defensive: callers passing the wrong object type get the default."""
    default = dw.DateWindow(start=date(2026, 1, 1), end_exclusive=date(2026, 1, 2))
    out = dw.parse_window(object(), default=default)
    assert out == default


def test_default_window_uses_clock_today(monkeypatch: pytest.MonkeyPatch) -> None:
    from service_crm.shared import clock

    fixed = datetime(2026, 5, 13, 12, 0, 0)
    monkeypatch.setattr(clock, "_now", lambda: fixed)
    w = dw.this_month()
    assert w.start == date(2026, 5, 1)
