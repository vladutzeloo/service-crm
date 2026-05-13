"""Tiny CSV writer for the reports blueprint.

RFC 4180-ish: ``\r\n`` line endings, UTF-8 without BOM, comma
separator, fields quoted on demand by :mod:`csv` from the standard
library. Headers translated at render time but the column order is
the report's stable identifier — column 1 is the English ``code``,
column 2 is the translated label, columns 3+ are the data.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable, Sequence
from typing import Any

from flask import Response

from ..shared.date_window import DateWindow


def write_csv(
    *,
    report_code: str,
    window: DateWindow,
    headers: Sequence[str],
    rows: Iterable[Sequence[Any]],
) -> Response:
    """Build a Flask :class:`Response` carrying a CSV body.

    ``report_code`` is the stable English identifier — used in the
    filename and as the first cell on every row when the report has a
    natural row-code (otherwise just rendered in the filename).
    """
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(list(headers))
    for row in rows:
        writer.writerow(list(row))
    body = buffer.getvalue().encode("utf-8")
    filename = f"{report_code.replace('_', '-')}-{window.iso_label()}.csv"
    return Response(
        body,
        mimetype="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"',
            "Content-Length": str(len(body)),
        },
    )


__all__ = ["write_csv"]
