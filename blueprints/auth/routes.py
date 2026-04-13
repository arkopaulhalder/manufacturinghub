"""
blueprints/auth/routes.py

US-1 routes: register, login, logout, forgot-password, reset-password.
All business logic delegated to auth_service — routes only handle
HTTP concerns (redirect, flash, render).
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, login_user, logout_user, current_user

from services.auth_service import (
    attempt_login,
    generate_reset_token,
    register_user,
    reset_password,
)

from . import auth_bp
from .forms import ForgotPasswordForm, LoginForm, RegisterForm, ResetPasswordForm


# ------------------------------------------------------------------ #
# Register — US-1                                                     #
# ------------------------------------------------------------------ #

@auth_bp.route("/register", methods=["GET", "POST"])
def register():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = RegisterForm()
    if form.validate_on_submit():
        success, message = register_user(
            email=form.email.data,
            password=form.password.data,
            role_str=form.role.data,
        )
        if success:
            flash(message, "success")
            return redirect(url_for("auth.login"))
        flash(message, "danger")

    return render_template("auth/register.html", form=form)


# ------------------------------------------------------------------ #
# Login — US-1                                                        #
# ------------------------------------------------------------------ #

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        success, message, user = attempt_login(
            email=form.email.data,
            password=form.password.data,
        )
        if success:
            login_user(user)
            # Open-redirect hardening: only allow same-site relative paths
            next_page = request.args.get("next")
            if next_page and next_page.startswith("/") and not next_page.startswith("//"):
                return redirect(next_page)
            return redirect(url_for("dashboard.index"))
        flash(message, "danger")

    return render_template("auth/login.html", form=form)


# ------------------------------------------------------------------ #
# Logout — US-1                                                       #
# ------------------------------------------------------------------ #

@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("You have been logged out.", "info")
    return redirect(url_for("auth.login"))


# ------------------------------------------------------------------ #
# Forgot password — US-1                                              #
# ------------------------------------------------------------------ #

@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    form = ForgotPasswordForm()
    if form.validate_on_submit():
        success, token = generate_reset_token(form.email.data)
        if success:
            _send_reset_email(form.email.data, token)
        # SRS Don't: always show the same message — never reveal if email exists
        flash("If that email is registered, a reset link has been sent.", "info")
        return redirect(url_for("auth.login"))

    return render_template("auth/forgot_password.html", form=form)


# ------------------------------------------------------------------ #
# Reset password — US-1                                               #
# ------------------------------------------------------------------ #

@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password_view(token):
    form = ResetPasswordForm()
    if form.validate_on_submit():
        success, message = reset_password(token, form.password.data)
        if success:
            flash(message, "success")
            return redirect(url_for("auth.login"))
        flash(message, "danger")
        return redirect(url_for("auth.forgot_password"))

    return render_template("auth/reset_password.html", form=form, token=token)


# ------------------------------------------------------------------ #
# Internal helper                                                     #
# ------------------------------------------------------------------ #

def _send_reset_email(email: str, token: str):
    """
    Send password reset email via Flask-Mail.

    url_for(_external=True) uses the active request host in dev.
    In production, SERVER_NAME must be set in .env so the link is correct.
    """
    from flask import current_app
    from flask_mail import Message
    from app import mail  # use the shared mail instance from app factory

    reset_url = url_for("auth.reset_password_view", token=token, _external=True)
    msg = Message(
        subject="ManufacturingHub — Password Reset",
        recipients=[email],
        body=(
            f"Hello,\n\n"
            f"Click the link below to reset your ManufacturingHub password.\n"
            f"This link expires in 1 hour.\n\n"
            f"{reset_url}\n\n"
            f"If you did not request a password reset, ignore this email."
        ),
    )
    try:
        mail.send(msg)
    except Exception as exc:
        current_app.logger.warning("Failed to send reset email to %s: %s", email, exc)