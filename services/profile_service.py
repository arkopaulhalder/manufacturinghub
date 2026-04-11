"""
services/profile_service.py

All US-2 business logic lives here.

US-2 acceptance criteria covered:
  - Profile fields: full_name, department, phone, email, notification_preference
  - Phone validation (10-digit format)
  - Updates audited with timestamp and user_id (via AuditLog)
  - Profile completion triggers role-based dashboard redirection (returns redirect url)
  - Pre-fill existing profile data (get_profile)
  - Do not allow special characters in department names
  - Do not expose other users' profiles without authorization
"""

import re

from models.audit import AuditLog, AuditAction
from models.base import db
from models.user import User, NotificationPreference


# ------------------------------------------------------------------ #
# Helpers                                                             #
# ------------------------------------------------------------------ #

def _is_valid_phone(phone: str) -> bool:
    """10-digit numeric string — per SRS."""
    return bool(re.fullmatch(r"\d{10}", phone))


def _is_valid_department(dept: str) -> bool:
    """No special characters allowed — per SRS Don't."""
    return bool(re.fullmatch(r"[A-Za-z0-9 ]+", dept))


def dashboard_url_for_role(user: User) -> str:
    """
    Returns the Flask url endpoint name for the user's role.
    Used after profile completion to redirect to the correct dashboard.
    """
    from models.user import UserRole
    if user.role == UserRole.MANAGER:
        return "dashboard.manager"
    return "dashboard.planner"


# ------------------------------------------------------------------ #
# US-2: Get profile (for pre-fill)                                    #
# ------------------------------------------------------------------ #

def get_profile(user_id: int, requesting_user_id: int) -> tuple[bool, str, User | None]:
    """
    Fetch a user's profile.
    SRS Don't: do not expose other users' profiles without authorization.
    Only the owner can view their own profile.
    """
    if user_id != requesting_user_id:
        return False, "Not authorized to view this profile.", None

    user = User.query.get(user_id)
    if not user:
        return False, "User not found.", None

    return True, "", user


# ------------------------------------------------------------------ #
# US-2: Update profile                                                #
# ------------------------------------------------------------------ #

def update_profile(
    user_id: int,
    requesting_user_id: int,
    full_name: str,
    department: str,
    phone: str,
    notification_preference: str,
    ip_address: str = None,
) -> tuple[bool, str]:
    """
    Validate and save profile fields.
    Writes an AuditLog row (timestamp + user_id) per SRS.
    """
    # Authorization — only owner can edit their own profile
    if user_id != requesting_user_id:
        return False, "Not authorized to edit this profile."

    user = User.query.get(user_id)
    if not user:
        return False, "User not found."

    # --- Validation ---
    if phone and not _is_valid_phone(phone):
        return False, "Phone must be exactly 10 digits."

    if department and not _is_valid_department(department):
        return False, "Department name must not contain special characters."

    try:
        pref = NotificationPreference[notification_preference.upper()]
    except KeyError:
        return False, "Invalid notification preference."

    # Capture old values for audit log
    old_values = {
        "full_name": user.full_name,
        "department": user.department,
        "phone": user.phone,
        "notification_preference": user.notification_preference.value if user.notification_preference else None,
    }

    # Apply updates
    user.full_name               = full_name.strip() if full_name else None
    user.department              = department.strip() if department else None
    user.phone                   = phone.strip() if phone else None
    user.notification_preference = pref

    new_values = {
        "full_name": user.full_name,
        "department": user.department,
        "phone": user.phone,
        "notification_preference": user.notification_preference.value,
    }

    # Audit log — timestamp is set automatically by the model default
    audit = AuditLog(
        user_id=user_id,
        action=AuditAction.USER_PROFILE_UPDATE,
        ip_address=ip_address,
        entity_type="User",
        entity_id=user_id,
        old_values=old_values,
        new_values=new_values,
    )
    db.session.add(audit)
    db.session.commit()

    return True, "Profile updated successfully."