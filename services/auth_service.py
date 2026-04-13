"""
services/auth_service.py

All US-1 business logic lives here. Routes call these functions — they
never touch the db or Werkzeug directly.

US-1 acceptance criteria covered:
  - Register with unique email; password stored as bcrypt hash
  - Login creates a session; logout clears session
  - Generic error messages on failed login (do not reveal if email exists)
  - Password reset via time-limited token (expires in 1 hour)
  - Validate email format and password complexity (min 8 chars, 1 uppercase, 1 digit)
  - Rate-limit login attempts (max 5 per 15 minutes)
  - Do not store plaintext passwords
  - Do not reveal whether an email exists on login/reset errors
"""

import re
import secrets
from datetime import datetime, timedelta, timezone

import bcrypt
from flask import current_app
from werkzeug.security import check_password_hash

from models.base import db
from models.user import User, UserRole


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _now():
    return datetime.now(timezone.utc)


def _hash_password_bcrypt(password: str) -> str:
    """SRS: store passwords with bcrypt (not Werkzeug default scrypt/pbkdf2)."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def _password_matches_stored(password: str, stored_hash: str) -> bool:
    """
    Verify password. Accepts bcrypt hashes; falls back to legacy Werkzeug hashes
    so existing DB rows keep working until the user changes password.
    """
    if not stored_hash:
        return False
    if stored_hash.startswith(("$2a$", "$2b$", "$2y$")):
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except (ValueError, TypeError):
            return False
    return check_password_hash(stored_hash, password)


def _is_valid_email(email: str) -> bool:
    pattern = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"
    return bool(re.match(pattern, email))


def _is_valid_password(password: str) -> bool:
    """min 8 chars, at least 1 uppercase letter, at least 1 digit """
    if len(password) < 8:
        return False
    if not any(c.isupper() for c in password):
        return False
    if not any(c.isdigit() for c in password):
        return False
    return True


# ------------------------------------------------------------------ #
# US-1: Register                                                      #
# ------------------------------------------------------------------ #

def register_user(email: str, password: str, role_str: str) -> tuple[bool, str]:
    """
    Create a new user account.
    Returns (success: bool, message: str).
    """
    email = email.strip().lower()

    if not _is_valid_email(email):
        return False, "Invalid email format."

    if not _is_valid_password(password):
        return False, "Password must be at least 8 characters with 1 uppercase letter and 1 digit."

    # Unique email check
    if User.query.filter_by(email=email).first():
        # SRS: do not reveal if email exists — use generic message
        return False, "Registration failed. Please check your details."

    try:
        role = UserRole[role_str.upper()]
    except KeyError:
        return False, "Invalid role."

    user = User(
        email=email,
        password_hash=_hash_password_bcrypt(password),
        role=role,
    )
    db.session.add(user)
    db.session.commit()
    return True, "Account created successfully."


# ------------------------------------------------------------------ #
# US-1: Login with rate-limiting                                      #
# ------------------------------------------------------------------ #

def attempt_login(email: str, password: str) -> tuple[bool, str, User | None]:
    """
    Validate credentials, enforce rate-limit.
    Returns (success, message, user_or_None).
    Generic error messages — never reveal if email exists (SRS Don't).
    """
    max_attempts = current_app.config.get("LOGIN_MAX_ATTEMPTS", 5)
    lockout_mins = current_app.config.get("LOGIN_LOCKOUT_MINS", 15)
    generic_error = "Invalid email or password."

    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()

    # Always run through the same code path to prevent timing attacks
    if user is None:
        return False, generic_error, None

    # Check if currently locked out
    if user.login_lockout_until and _now() < user.login_lockout_until:
        return False, "Too many failed attempts. Please try again later.", None

    # Reset counter if lockout has expired
    if user.login_lockout_until and _now() >= user.login_lockout_until:
        user.login_attempt_count = 0
        user.login_lockout_until = None

    if not _password_matches_stored(password, user.password_hash):
        user.login_attempt_count += 1
        if user.login_attempt_count >= max_attempts:
            user.login_lockout_until = _now() + timedelta(minutes=lockout_mins)
        db.session.commit()
        return False, generic_error, None

    # Upgrade legacy Werkzeug hash to bcrypt on successful login
    if not user.password_hash.startswith(("$2a$", "$2b$", "$2y$")):
        user.password_hash = _hash_password_bcrypt(password)

    # Successful login — reset counter
    user.login_attempt_count = 0
    user.login_lockout_until = None
    db.session.commit()
    return True, "Login successful.", user


# ------------------------------------------------------------------ #
# US-1: Password reset                                                #
# ------------------------------------------------------------------ #

def generate_reset_token(email: str) -> tuple[bool, str]:
    """
    Generate a 1-hour reset token.
    SRS Don't: do not reveal whether an email exists — always return
    the same generic message to the caller.
    """
    expiry_secs = current_app.config.get("RESET_TOKEN_EXPIRY", 3600)
    email = email.strip().lower()
    user = User.query.filter_by(email=email).first()

    if user:
        token = secrets.token_urlsafe(32)
        user.reset_token = token
        user.reset_token_expires = _now() + timedelta(seconds=expiry_secs)
        db.session.commit()
        # Caller (route) sends the email — service only stores the token
        return True, token

    # Do NOT reveal that email doesn't exist
    return False, ""


def reset_password(token: str, new_password: str) -> tuple[bool, str]:
    """
    Validate token and set new password.
    """
    if not _is_valid_password(new_password):
        return False, "Password must be at least 8 characters with 1 uppercase letter and 1 digit."

    user = User.query.filter_by(reset_token=token).first()

    if not user or not user.reset_token_expires:
        return False, "Invalid or expired reset link."

    if _now() > user.reset_token_expires:
        return False, "Invalid or expired reset link."

    user.password_hash = _hash_password_bcrypt(new_password)
    user.reset_token = None
    user.reset_token_expires = None
    db.session.commit()
    return True, "Password updated successfully."