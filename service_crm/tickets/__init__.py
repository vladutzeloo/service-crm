"""Tickets blueprint.

Owns the ticket workflow for ROADMAP 0.5.0: ``ServiceTicket``, the
append-only ``TicketStatusHistory``, ``TicketComment`` /
``TicketAttachment``, and the ``TicketType`` / ``TicketPriority``
lookups. Mounted under ``/tickets``.

The state machine in ``state.py`` is pure Python so it can be exercised
with Hypothesis without a session. The audit-of-record for status
changes is :class:`TicketStatusHistory`; rows are written by the
``before_flush`` hook in ``service_crm.shared.audit`` so any code path
that mutates ``ServiceTicket.status`` automatically produces history.
"""

from __future__ import annotations

from flask import Blueprint

bp = Blueprint(
    "tickets",
    __name__,
    url_prefix="/tickets",
    template_folder="../templates/tickets",
)

from . import models, routes  # noqa: E402, F401

__all__ = ["bp"]
