"""Date-window parser + presets for dashboards and reports.

ROADMAP 0.8.0. Used by :mod:`service_crm.dashboard` and
:mod:`service_crm.reports` to turn the standard ``?from=YYYY-MM-DD``
+ ``?to=YYYY-MM-DD`` query pair into a normalised
``(start, end_exclusive)`` tuple.

Conventions:

- All windows are **half-open**: ``[start, end_exclusive)``. A query
  for "May 1st through May 13th" yields ``(2026-05-01, 2026-05-14)``
  so SQL ranges read ``column >= start AND column < end_exclusive``
  uniformly without off-by-one fiddling.
- A missing or malformed value falls back to the default window
  rather than raising — these helpers serve read-only views; bad
  user input shouldn't 500.
- Week starts Monday (ISO 8601) per blueprint §13 (Romanian default
  locale).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, timedelta

from . import clock


@dataclass(frozen=True)
class DateWindow:
    """A half-open ``[start, end_exclusive)`` interval."""

    start: date
    end_exclusive: date

    @property
    def end_inclusive(self) -> date:
        """The last day inside the window (used for display only)."""
        return self.end_exclusive - timedelta(days=1)

    @property
    def days(self) -> int:
        """Number of days inside the window (always ≥ 1)."""
        return (self.end_exclusive - self.start).days

    def contains(self, day: date) -> bool:
        return self.start <= day < self.end_exclusive

    def iso_label(self) -> str:
        """Compact ISO label used for CSV filenames."""
        return f"{self.start.strftime('%Y%m%d')}-{self.end_inclusive.strftime('%Y%m%d')}"


def _today() -> date:
    return clock.now().date()


def this_week(*, today: date | None = None) -> DateWindow:
    """Monday-to-next-Monday window covering the current week."""
    ref = today or _today()
    start = ref - timedelta(days=ref.weekday())
    return DateWindow(start=start, end_exclusive=start + timedelta(days=7))


_DECEMBER = 12


def this_month(*, today: date | None = None) -> DateWindow:
    """First-of-month-to-first-of-next-month window."""
    ref = today or _today()
    start = ref.replace(day=1)
    if start.month == _DECEMBER:
        end_exclusive = date(start.year + 1, 1, 1)
    else:
        end_exclusive = date(start.year, start.month + 1, 1)
    return DateWindow(start=start, end_exclusive=end_exclusive)


def last_n_days(n: int, *, today: date | None = None) -> DateWindow:
    """A rolling ``n``-day window ending tomorrow (exclusive)."""
    if n <= 0:
        raise ValueError("n must be positive")
    ref = today or _today()
    return DateWindow(start=ref - timedelta(days=n - 1), end_exclusive=ref + timedelta(days=1))


def _parse_iso_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value)
    except ValueError:
        return None


def parse_window(
    args: object,
    *,
    default: DateWindow | None = None,
    today: date | None = None,
) -> DateWindow:
    """Build a :class:`DateWindow` from a query-args mapping.

    Reads ``from`` / ``to`` if both present and well-formed; otherwise
    returns ``default`` (or :func:`this_month` if no default given).
    Accepts Werkzeug's ``ImmutableMultiDict`` and any
    ``mapping.get(key) -> str | None``; declared as ``object`` so the
    signature isn't tied to Werkzeug's import path.
    """
    get = getattr(args, "get", None)
    raw_from = get("from") if callable(get) else None
    raw_to = get("to") if callable(get) else None
    start = _parse_iso_date(raw_from)
    end_inclusive = _parse_iso_date(raw_to)
    if start is None or end_inclusive is None:
        return default if default is not None else this_month(today=today)
    if end_inclusive < start:
        start, end_inclusive = end_inclusive, start
    return DateWindow(start=start, end_exclusive=end_inclusive + timedelta(days=1))


__all__ = [
    "DateWindow",
    "last_n_days",
    "parse_window",
    "this_month",
    "this_week",
]
