"""Tests for the CSV writer used by the reports blueprint."""

from __future__ import annotations

from datetime import date

import pytest
from flask import Flask

from service_crm.reports.csv import write_csv
from service_crm.shared.date_window import DateWindow


@pytest.fixture
def window() -> DateWindow:
    return DateWindow(start=date(2026, 5, 1), end_exclusive=date(2026, 5, 14))


def test_write_csv_returns_text_csv_response(window: DateWindow) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        resp = write_csv(
            report_code="tickets_by_status",
            window=window,
            headers=["bucket", "code", "count"],
            rows=[("2026-05-01", "new", 3)],
        )
    assert resp.mimetype == "text/csv"
    assert "charset=utf-8" in resp.headers["Content-Type"]


def test_write_csv_filename_includes_window(window: DateWindow) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        resp = write_csv(
            report_code="tickets_by_status",
            window=window,
            headers=["bucket"],
            rows=[("2026-05-01",)],
        )
    disposition = resp.headers["Content-Disposition"]
    assert "tickets-by-status-20260501-20260513.csv" in disposition


def test_write_csv_emits_crlf_line_endings(window: DateWindow) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        resp = write_csv(
            report_code="tickets_by_status",
            window=window,
            headers=["a", "b"],
            rows=[("1", "2"), ("3", "4")],
        )
    body = resp.get_data(as_text=True)
    assert "\r\n" in body
    # No bare ``\n`` outside of CRLF — every newline is preceded by CR.
    assert "\n" not in body.replace("\r\n", "")


def test_write_csv_renders_headers_first(window: DateWindow) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        resp = write_csv(
            report_code="tickets_by_status",
            window=window,
            headers=["bucket", "code", "count"],
            rows=[("2026-05-01", "new", 3)],
        )
    body = resp.get_data(as_text=True)
    first_line = body.splitlines()[0]
    assert first_line == "bucket,code,count"


def test_write_csv_handles_empty_rows(window: DateWindow) -> None:
    app = Flask(__name__)
    with app.test_request_context():
        resp = write_csv(
            report_code="parts_used",
            window=window,
            headers=["part_code", "quantity"],
            rows=[],
        )
    body = resp.get_data(as_text=True)
    assert body.strip() == "part_code,quantity"
