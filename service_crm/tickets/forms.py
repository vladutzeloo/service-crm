"""Flask-WTF forms for the tickets blueprint.

All forms inherit ``FlaskForm`` so they pick up the project's CSRF
behaviour and the ``form_shell`` idempotency-token wiring. SELECT
fields use ``validate_choice=False`` because their choices are
populated by the route from the current DB state; the service layer is
the source of truth for the referenced FK existing.
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    DateTimeLocalField,
    SelectField,
    SelectMultipleField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


class TicketCreateForm(FlaskForm):  # type: ignore[misc]
    client_id = SelectField(
        _l("Client"), validators=[DataRequired()], choices=[], validate_choice=False
    )
    equipment_id = SelectField(
        _l("Equipment"), validators=[Optional()], choices=[], validate_choice=False
    )
    type_id = SelectField(
        _l("Type"), validators=[Optional()], choices=[], validate_choice=False
    )
    priority_id = SelectField(
        _l("Priority"), validators=[Optional()], choices=[], validate_choice=False
    )
    assignee_user_id = SelectField(
        _l("Assignee"), validators=[Optional()], choices=[], validate_choice=False
    )
    title = StringField(_l("Title"), validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(_l("Description"), validators=[Optional(), Length(max=8000)])
    due_at = DateTimeLocalField(
        _l("Due at"), validators=[Optional()], format="%Y-%m-%dT%H:%M"
    )
    sla_due_at = DateTimeLocalField(
        _l("SLA due at"), validators=[Optional()], format="%Y-%m-%dT%H:%M"
    )
    submit = SubmitField(_l("Save"))


class TicketEditForm(TicketCreateForm):
    """Same fields as the create form; ``client_id`` is unchangeable
    after creation (no field on the page) so subclassing keeps the
    rendering logic identical."""


class TicketTransitionForm(FlaskForm):  # type: ignore[misc]
    to_state = SelectField(
        _l("Move to"), validators=[DataRequired()], choices=[], validate_choice=False
    )
    reason_code = SelectField(
        _l("Reason code"),
        validators=[Optional()],
        choices=[
            ("", _l("— none —")),
            ("resolved_remotely", _l("Resolved remotely")),
            ("client_request", _l("Client request")),
            ("duplicate", _l("Duplicate")),
            ("no_fault_found", _l("No fault found")),
            ("out_of_scope", _l("Out of scope")),
            ("other", _l("Other")),
        ],
        validate_choice=False,
    )
    reason = TextAreaField(_l("Reason"), validators=[Optional(), Length(max=2000)])
    submit = SubmitField(_l("Apply"))


class TicketFilterForm(FlaskForm):  # type: ignore[misc]
    """Filter-bar form. Submits GET; never carries CSRF."""

    class Meta:
        csrf = False

    q = StringField(_l("Search"), validators=[Optional(), Length(max=200)])
    status = SelectMultipleField(
        _l("Status"), validators=[Optional()], choices=[], validate_choice=False
    )
    type_id = SelectField(
        _l("Type"), validators=[Optional()], choices=[], validate_choice=False
    )
    priority_id = SelectField(
        _l("Priority"), validators=[Optional()], choices=[], validate_choice=False
    )
    submit = SubmitField(_l("Filter"))


class TicketCommentForm(FlaskForm):  # type: ignore[misc]
    body = TextAreaField(
        _l("Comment"), validators=[DataRequired(), Length(max=8000)]
    )
    submit = SubmitField(_l("Add"))


class TicketAttachmentForm(FlaskForm):  # type: ignore[misc]
    upload = FileField(
        _l("Attachment"),
        validators=[
            FileRequired(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "gif", "pdf", "txt", "csv"],
                _l("Allowed: images, PDFs, plain text, CSV."),
            ),
        ],
    )
    submit = SubmitField(_l("Upload"))


class TicketAttachmentDeleteForm(FlaskForm):  # type: ignore[misc]
    reason = StringField(_l("Reason"), validators=[DataRequired(), Length(max=200)])
    submit = SubmitField(_l("Delete"))


class TicketLookupEditForm(FlaskForm):  # type: ignore[misc]
    label = StringField(_l("Label"), validators=[DataRequired(), Length(max=120)])
    is_active = SelectField(
        _l("Active"),
        validators=[DataRequired()],
        choices=[("1", _l("Active")), ("0", _l("Inactive"))],
    )
    submit = SubmitField(_l("Save"))
