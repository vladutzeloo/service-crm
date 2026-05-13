"""Flask-WTF forms for the planning blueprint."""

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


class TechnicianCreateForm(FlaskForm):  # type: ignore[misc]
    user_id = SelectField(
        _l("User"),
        choices=[],
        validate_choice=False,
        validators=[DataRequired()],
    )
    display_name = StringField(_l("Display name"), validators=[Optional(), Length(max=200)])
    timezone = StringField(
        _l("Timezone"),
        default="Europe/Bucharest",
        validators=[Optional(), Length(max=60)],
    )
    weekly_capacity_minutes = IntegerField(
        _l("Weekly capacity (minutes)"),
        default=2400,
        validators=[DataRequired(), NumberRange(min=0, max=100_000)],
    )
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    submit = SubmitField(_l("Save"))


class TechnicianEditForm(FlaskForm):  # type: ignore[misc]
    display_name = StringField(_l("Display name"), validators=[Optional(), Length(max=200)])
    timezone = StringField(_l("Timezone"), validators=[Optional(), Length(max=60)])
    weekly_capacity_minutes = IntegerField(
        _l("Weekly capacity (minutes)"),
        validators=[DataRequired(), NumberRange(min=0, max=100_000)],
    )
    notes = TextAreaField(_l("Notes"), validators=[Optional(), Length(max=8000)])
    is_active = BooleanField(_l("Active"), default=True)
    submit = SubmitField(_l("Save"))


class CapacitySlotForm(FlaskForm):  # type: ignore[misc]
    day = DateField(_l("Day"), validators=[DataRequired()])
    capacity_minutes = IntegerField(
        _l("Capacity (minutes)"),
        validators=[DataRequired(), NumberRange(min=0, max=24 * 60)],
    )
    notes = StringField(_l("Notes"), validators=[Optional(), Length(max=200)])
    submit = SubmitField(_l("Save"))


class CapacityRangeForm(FlaskForm):  # type: ignore[misc]
    start = DateField(_l("Start"), validators=[Optional()])
    end = DateField(_l("End"), validators=[Optional()])
    submit = SubmitField(_l("Filter"))

    class Meta:
        # No CSRF protection on a pure-GET filter form.
        csrf = False


__all__ = [
    "CapacityRangeForm",
    "CapacitySlotForm",
    "TechnicianCreateForm",
    "TechnicianEditForm",
]
