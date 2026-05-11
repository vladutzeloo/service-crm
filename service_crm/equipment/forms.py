"""Flask-WTF forms for the equipment blueprint.

``EquipmentForm`` keeps the ``client_id`` and ``location_id`` choice
fields populated dynamically from the route — passing them through the
constructor keeps the form pure (no DB session at import time).
"""

from __future__ import annotations

from flask_babel import lazy_gettext as _
from flask_wtf import FlaskForm
from flask_wtf.file import FileAllowed, FileField, FileRequired
from wtforms import (
    DateField,
    SelectField,
    StringField,
    SubmitField,
    TextAreaField,
)
from wtforms.validators import DataRequired, Length, Optional


class ControllerTypeForm(FlaskForm):  # type: ignore[misc]
    code = StringField(_("Code"), validators=[DataRequired(), Length(max=40)])
    name = StringField(_("Name"), validators=[DataRequired(), Length(max=120)])
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class EquipmentModelForm(FlaskForm):  # type: ignore[misc]
    manufacturer = StringField(_("Manufacturer"), validators=[DataRequired(), Length(max=120)])
    model_code = StringField(_("Model code"), validators=[DataRequired(), Length(max=120)])
    display_name = StringField(_("Display name"), validators=[Optional(), Length(max=200)])
    controller_type_id = SelectField(
        _("Controller type"), validators=[Optional()], choices=[], validate_choice=False
    )
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class EquipmentForm(FlaskForm):  # type: ignore[misc]
    # ``validate_choice=False`` on the FK fields keeps WTForms from rejecting
    # values that aren't in the dynamically-populated dropdown. The service
    # layer is the source of truth for the "location belongs to this client"
    # invariant (see services._validate_location_belongs_to_client) and for
    # checking the referenced model / controller exist.
    client_id = SelectField(
        _("Client"), validators=[DataRequired()], choices=[], validate_choice=False
    )
    location_id = SelectField(
        _("Location"), validators=[Optional()], choices=[], validate_choice=False
    )
    equipment_model_id = SelectField(
        _("Model"), validators=[Optional()], choices=[], validate_choice=False
    )
    controller_type_id = SelectField(
        _("Controller type"), validators=[Optional()], choices=[], validate_choice=False
    )
    serial_number = StringField(_("Serial number"), validators=[Optional(), Length(max=120)])
    asset_tag = StringField(_("Asset tag"), validators=[Optional(), Length(max=80)])
    install_date = DateField(_("Install date"), validators=[Optional()])
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class WarrantyForm(FlaskForm):  # type: ignore[misc]
    reference = StringField(_("Reference"), validators=[Optional(), Length(max=120)])
    provider = StringField(_("Provider"), validators=[Optional(), Length(max=160)])
    starts_on = DateField(_("Starts on"), validators=[DataRequired()])
    ends_on = DateField(_("Ends on"), validators=[DataRequired()])
    notes = TextAreaField(_("Notes"), validators=[Optional(), Length(max=4000)])
    submit = SubmitField(_("Save"))


class ImportCsvForm(FlaskForm):  # type: ignore[misc]
    csv_file = FileField(
        _("CSV file"),
        validators=[
            FileRequired(),
            FileAllowed(["csv"], _("CSV files only.")),
        ],
    )
    submit = SubmitField(_("Import"))
