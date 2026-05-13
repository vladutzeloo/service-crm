"""Flask-WTF forms for the intervention / parts surface of tickets."""

from __future__ import annotations

from flask_babel import lazy_gettext as _l
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    BooleanField,
    DateTimeLocalField,
    IntegerField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class InterventionCreateForm(FlaskForm):  # type: ignore[misc]
    technician_user_id = SelectField(
        _l("Technician"),
        validators=[Optional()],
        choices=[],
        validate_choice=False,
    )
    started_at = DateTimeLocalField(
        _l("Started at"),
        validators=[Optional()],
        format="%Y-%m-%dT%H:%M",
    )
    summary = TextAreaField(_l("Summary"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class InterventionEditForm(FlaskForm):  # type: ignore[misc]
    technician_user_id = SelectField(
        _l("Technician"),
        validators=[Optional()],
        choices=[],
        validate_choice=False,
    )
    started_at = DateTimeLocalField(
        _l("Started at"),
        validators=[DataRequired()],
        format="%Y-%m-%dT%H:%M",
    )
    ended_at = DateTimeLocalField(
        _l("Ended at"),
        validators=[Optional()],
        format="%Y-%m-%dT%H:%M",
    )
    summary = TextAreaField(_l("Summary"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class InterventionStopForm(FlaskForm):  # type: ignore[misc]
    submit = SubmitField(_l("Stop"))


class InterventionActionForm(FlaskForm):  # type: ignore[misc]
    description = TextAreaField(
        _l("Action"),
        validators=[DataRequired(), Length(max=4000)],
    )
    duration_minutes = IntegerField(
        _l("Duration (minutes)"),
        validators=[Optional(), NumberRange(min=0, max=10_000)],
    )
    submit = SubmitField(_l("Add"))


class InterventionFindingForm(FlaskForm):  # type: ignore[misc]
    description = TextAreaField(
        _l("Finding"),
        validators=[DataRequired(), Length(max=4000)],
    )
    is_root_cause = BooleanField(_l("Root cause"), default=False)
    submit = SubmitField(_l("Add"))


class InterventionPartUsageForm(FlaskForm):  # type: ignore[misc]
    part_id = SelectField(
        _l("Part"),
        validators=[Optional()],
        choices=[],
        validate_choice=False,
    )
    part_code = StringField(_l("Code"), validators=[Optional(), Length(max=80)])
    description = StringField(_l("Description"), validators=[Optional(), Length(max=200)])
    quantity = IntegerField(
        _l("Quantity"),
        validators=[DataRequired(), NumberRange(min=1, max=10_000)],
        default=1,
    )
    unit = StringField(_l("Unit"), validators=[Optional(), Length(max=20)], default="pcs")
    submit = SubmitField(_l("Add"))


class InterventionPhotoForm(FlaskForm):  # type: ignore[misc]
    upload = FileField(
        _l("Photo"),
        validators=[
            FileRequired(),
            FileAllowed(
                ["jpg", "jpeg", "png", "webp", "gif"],
                _l("Allowed: images."),
            ),
        ],
    )
    submit = SubmitField(_l("Upload"))


class PartCreateForm(FlaskForm):  # type: ignore[misc]
    code = StringField(_l("Code"), validators=[DataRequired(), Length(max=80)])
    description = StringField(_l("Description"), validators=[Optional(), Length(max=200)])
    unit = StringField(_l("Unit"), validators=[Optional(), Length(max=20)], default="pcs")
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class PartEditForm(FlaskForm):  # type: ignore[misc]
    description = StringField(_l("Description"), validators=[Optional(), Length(max=200)])
    unit = StringField(_l("Unit"), validators=[Optional(), Length(max=20)], default="pcs")
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save"))
