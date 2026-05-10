"""Tests for service_crm.shared.clock."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from service_crm.shared import clock


@pytest.mark.unit
def test_now_returns_timezone_aware_datetime() -> None:
    value = clock.now()
    assert isinstance(value, datetime)
    assert value.tzinfo is not None


@pytest.mark.unit
def test_now_uses_utc() -> None:
    value = clock.now()
    assert value.utcoffset() == UTC.utcoffset(value)


@pytest.mark.unit
def test_frozen_clock_pins_now(frozen_clock: datetime) -> None:
    assert clock.now() == frozen_clock
