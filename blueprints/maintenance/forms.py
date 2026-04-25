"""
blueprints/maintenance/forms.py — US-7 Maintenance forms.

SRS acceptance criteria:
  - Define maintenance rules: machine_id, frequency, interval
  - Log maintenance: date, performed_by, notes

SRS Don'ts:
  - Do not allow maintenance intervals < 1 day or < 10 hours
    (validated in service layer based on frequency)
"""

from flask_wtf import FlaskForm
from wtforms import (
    DateTimeLocalField, IntegerField, SelectField, StringField,
    SubmitField, TextAreaField,
)
from wtforms.validators import DataRequired, Length, NumberRange, Optional


class MaintenanceRuleForm(FlaskForm):
    """Form for creating/editing a maintenance rule."""
    machine_id = SelectField(
        "Machine",
        coerce=int,
        validators=[DataRequired()],
    )
    frequency = SelectField(
        "Frequency Type",
        choices=[
            ("DATE_BASED", "Date-based (days)"),
            ("HOURS_BASED", "Hours-based (runtime hours)"),
        ],
        validators=[DataRequired()],
    )
    interval_value = IntegerField(
        "Interval",
        validators=[
            DataRequired(),
            NumberRange(min=1, message="Interval must be at least 1."),
        ],
        description="Days (for date-based) or hours (for hours-based)",
    )
    last_maintenance_date = DateTimeLocalField(
        "Last Maintenance Date",
        format="%Y-%m-%dT%H:%M",
        validators=[Optional()],
        description="Leave blank if no prior maintenance recorded",
    )
    submit = SubmitField("Save Rule")


class MaintenanceLogForm(FlaskForm):
    """Form for logging completed maintenance."""
    date = DateTimeLocalField(
        "Maintenance Date",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired()],
    )
    performed_by = StringField(
        "Performed By",
        validators=[DataRequired(), Length(max=255)],
        description="Name of technician or team",
    )
    notes = TextAreaField(
        "Notes",
        validators=[Optional(), Length(max=2000)],
        description="Optional details about the maintenance performed",
    )
    submit = SubmitField("Log Maintenance")
