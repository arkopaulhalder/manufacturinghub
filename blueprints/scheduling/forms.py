"""
blueprints/scheduling/forms.py — US-5 Production Scheduling form.

SRS fields:
  - machine: select from ACTIVE machines only
  - scheduled_start: datetime picker (date + time)

estimated_hours is calculated server-side:
  CEIL(quantity / machine.capacity_per_hour)
  Not a form field — computed in the service.
"""

from flask_wtf import FlaskForm
from wtforms import DateTimeLocalField, SelectField, SubmitField
from wtforms.validators import DataRequired


class ScheduleForm(FlaskForm):
    machine_id = SelectField(
        "Machine",
        coerce=int,
        validators=[DataRequired(message="Please select a machine.")],
    )
    scheduled_start = DateTimeLocalField(
        "Start Date & Time",
        format="%Y-%m-%dT%H:%M",
        validators=[DataRequired(message="Please select a start date and time.")],
    )
    submit = SubmitField("Schedule Order")