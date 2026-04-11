"""
blueprints/auth/forms.py

Flask-WTF forms for US-1.
All validation rules match SRS acceptance criteria exactly.
CSRF is enabled globally via Flask-WTF — no extra code needed here.
"""

from flask_wtf import FlaskForm
from wtforms import EmailField, PasswordField, SelectField, StringField, SubmitField
from wtforms.validators import DataRequired, Email, EqualTo, Length, Regexp


class RegisterForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email(), Length(max=254)],
    )
    password = PasswordField(
        "Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
            # 1 uppercase + 1 digit — matches SRS Dos
            Regexp(
                r"^(?=.*[A-Z])(?=.*\d).+$",
                message="Password must contain at least 1 uppercase letter and 1 digit.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    role = SelectField(
        "Role",
        choices=[("PLANNER", "Production Planner"), ("MANAGER", "Plant Manager")],
        validators=[DataRequired()],
    )
    submit = SubmitField("Register")


class LoginForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()],
    )
    password = PasswordField(
        "Password",
        validators=[DataRequired()],
    )
    submit = SubmitField("Login")


class ForgotPasswordForm(FlaskForm):
    email = EmailField(
        "Email",
        validators=[DataRequired(), Email()],
    )
    submit = SubmitField("Send Reset Link")


class ResetPasswordForm(FlaskForm):
    password = PasswordField(
        "New Password",
        validators=[
            DataRequired(),
            Length(min=8, message="Password must be at least 8 characters."),
            Regexp(
                r"^(?=.*[A-Z])(?=.*\d).+$",
                message="Password must contain at least 1 uppercase letter and 1 digit.",
            ),
        ],
    )
    confirm_password = PasswordField(
        "Confirm New Password",
        validators=[DataRequired(), EqualTo("password", message="Passwords must match.")],
    )
    submit = SubmitField("Reset Password")