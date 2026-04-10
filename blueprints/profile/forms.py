from flask_wtf import FlaskForm
from wtforms import StringField, SubmitField, SelectField
from wtforms.validators import DataRequired, Email, Length, Regexp, ValidationError

class ProfileForm(FlaskForm):
    full_name = StringField('Full Name', validators=[DataRequired(), Length(max=100)])
    department = StringField('Department', validators=[
        DataRequired(), 
        Regexp(r'^[a-zA-Z\s]+$', message="Department must contain only letters and spaces.")
    ])
    phone = StringField('Phone', validators=[
        DataRequired(), 
        Regexp(r'^\d{10}$', message="Phone must be exactly 10 digits.")
    ])
    notification_preference = SelectField('Notification Preference', choices=[
        ('EMAIL', 'Email'),
        ('SMS', 'SMS'),
        ('NONE', 'None')
    ])
    submit = SubmitField('Update Profile')
