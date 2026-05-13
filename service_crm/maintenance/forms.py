"""Flask-WTF forms for the maintenance blueprint."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from wtforms import (
    BooleanField,
    DateField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class TemplateCreateForm(FlaskForm):  # type: ignore[misc]
    name = StringField(_l("Name"), validators=[DataRequired(), Length(max=200)])
    description = TextAreaField(_l("Description"), validators=[Optional(), Length(max=8000)])
    cadence_days = IntegerField(
        _l("Cadence (days)"),
        default=180,
        validators=[DataRequired(), NumberRange(min=1, max=3650)],
    )
    estimated_minutes = IntegerField(
        _l("Estimated minutes"),
        validators=[Optional(), NumberRange(min=0, max=10_000)],
    )
    checklist_template_id = SelectField(
        _l("Checklist template"),
        choices=[],
        validate_choice=False,
        validators=[Optional()],
    )
    submit = SubmitField(_l("Save"))


class TemplateEditForm(TemplateCreateForm):
    is_active = BooleanField(_l("Active"), default=True)


class PlanCreateForm(FlaskForm):  # type: ignore[misc]
    equipment_id = SelectField(
        _l("Equipment"),
        choices=[],
        validate_choice=False,
        validators=[DataRequired()],
    )
    template_id = SelectField(
        _l("Template"),
        choices=[],
        validate_choice=False,
        validators=[DataRequired()],
    )
    cadence_days = IntegerField(
        _l("Cadence (days)"),
        validators=[Optional(), NumberRange(min=1, max=3650)],
    )
    last_done_on = DateField(_l("Last done on"), validators=[Optional()])
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class PlanEditForm(FlaskForm):  # type: ignore[misc]
    cadence_days = IntegerField(
        _l("Cadence (days)"),
        validators=[DataRequired(), NumberRange(min=1, max=3650)],
    )
    last_done_on = DateField(_l("Last done on"), validators=[Optional()])
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save"))


class TaskAssignForm(FlaskForm):  # type: ignore[misc]
    technician_id = SelectField(
        _l("Technician"),
        choices=[],
        validate_choice=False,
        validators=[Optional()],
    )
    submit = SubmitField(_l("Save"))


class TaskCompleteForm(FlaskForm):  # type: ignore[misc]
    intervention_id = SelectField(
        _l("Linked intervention"),
        choices=[],
        validate_choice=False,
        validators=[Optional()],
    )
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Mark done"))


class TaskEscalateForm(FlaskForm):  # type: ignore[misc]
    title = StringField(_l("Ticket title"), validators=[Optional(), Length(max=200)])
    description = TextAreaField(
        _l("Ticket description"),
        validators=[Optional(), Length(max=8000)],
    )
    submit = SubmitField(_l("Open ticket"))


__all__ = [
    "PlanCreateForm",
    "PlanEditForm",
    "TaskAssignForm",
    "TaskCompleteForm",
    "TaskEscalateForm",
    "TemplateCreateForm",
    "TemplateEditForm",
]
