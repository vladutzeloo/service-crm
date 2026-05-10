"""Tests for service_crm.shared.ulid."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from service_crm.shared import ulid


@pytest.mark.unit
def test_new_returns_16_bytes() -> None:
    value = ulid.new()
    assert isinstance(value, bytes)
    assert len(value) == 16


@pytest.mark.unit
def test_new_values_are_unique() -> None:
    samples = {ulid.new() for _ in range(100)}
    assert len(samples) == 100


@pytest.mark.unit
def test_encode_decode_round_trip() -> None:
    value = ulid.new()
    assert ulid.decode(ulid.encode(value)) == value


@pytest.mark.unit
def test_encode_produces_26_char_uppercase_string() -> None:
    encoded = ulid.encode(ulid.new())
    assert len(encoded) == 26
    assert encoded.isupper()


@pytest.mark.unit
def test_decode_rejects_short_string() -> None:
    with pytest.raises(ValueError):
        ulid.decode("ABC")


@pytest.mark.unit
def test_decode_rejects_invalid_character() -> None:
    bad = "!" + "0" * 25
    with pytest.raises(ValueError):
        ulid.decode(bad)


@pytest.mark.unit
def test_encode_rejects_wrong_length() -> None:
    with pytest.raises(ValueError):
        ulid.encode(b"\x00" * 8)


@pytest.mark.unit
def test_time_prefix_increases_with_clock(monkeypatch: pytest.MonkeyPatch) -> None:
    """The 6-byte time prefix encodes the wall-clock millisecond, so a
    later clock reading produces a strictly larger prefix."""
    early = datetime(2026, 1, 1, 12, 0, 0, tzinfo=UTC)
    late = datetime(2026, 1, 1, 12, 0, 1, tzinfo=UTC)

    monkeypatch.setattr("service_crm.shared.clock._now", lambda: early)
    a = ulid.new()
    monkeypatch.setattr("service_crm.shared.clock._now", lambda: late)
    b = ulid.new()
    assert a[: ulid.TIME_BYTES] < b[: ulid.TIME_BYTES]


# --- ULID type bind/result hooks --------------------------------------------
# Exercised directly here so we don't need a live engine to cover them; the
# end-to-end path (SQLAlchemy column → DB → Python) is tested in /data-model.


def _dialect(name: str) -> object:
    """Stand-in dialect just exposing the ``name`` attribute the type uses."""

    class _D:
        pass

    d = _D()
    d.name = name  # type: ignore[attr-defined]
    return d


@pytest.mark.unit
def test_type_bind_sqlite_returns_raw_bytes() -> None:
    t = ulid.ULID()
    raw = ulid.new()
    assert t.process_bind_param(raw, _dialect("sqlite")) == raw  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_bind_postgres_returns_hex_string() -> None:
    t = ulid.ULID()
    raw = ulid.new()
    assert t.process_bind_param(raw, _dialect("postgresql")) == raw.hex()  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_bind_none_passes_through() -> None:
    t = ulid.ULID()
    assert t.process_bind_param(None, _dialect("sqlite")) is None  # type: ignore[arg-type]
    assert t.process_bind_param(None, _dialect("postgresql")) is None  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_bind_rejects_wrong_length() -> None:
    t = ulid.ULID()
    with pytest.raises(ValueError):
        t.process_bind_param(b"\x00" * 8, _dialect("sqlite"))  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_result_sqlite_returns_raw_bytes() -> None:
    t = ulid.ULID()
    raw = ulid.new()
    assert t.process_result_value(raw, _dialect("sqlite")) == raw  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_result_postgres_decodes_hex_with_dashes() -> None:
    t = ulid.ULID()
    raw = ulid.new()
    hex_with_dashes = (
        f"{raw[0:4].hex()}-{raw[4:6].hex()}-{raw[6:8].hex()}-{raw[8:10].hex()}-{raw[10:16].hex()}"
    )
    assert t.process_result_value(hex_with_dashes, _dialect("postgresql")) == raw  # type: ignore[arg-type]


@pytest.mark.unit
def test_type_result_none_passes_through() -> None:
    t = ulid.ULID()
    assert t.process_result_value(None, _dialect("sqlite")) is None  # type: ignore[arg-type]
    assert t.process_result_value(None, _dialect("postgresql")) is None  # type: ignore[arg-type]


@pytest.mark.unit
def test_load_dialect_impl_postgres_returns_pg_uuid() -> None:
    from sqlalchemy.dialects import postgresql, sqlite

    t = ulid.ULID()
    pg = postgresql.dialect()
    sl = sqlite.dialect()
    # SQLAlchemy 2.0 names the type ``PGUuid``; older versions used ``UUID``.
    assert "uuid" in t.load_dialect_impl(pg).__class__.__name__.lower()
    assert t.load_dialect_impl(sl).__class__.__name__ == "BINARY"
