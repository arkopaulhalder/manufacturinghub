"""
User model — covers US-1 (Authentication) and US-2 (User Profile).

Fields come directly from the SRS:
  - US-1 acceptance criteria: unique email, bcrypt password, role
  - US-2 acceptance criteria: full_name, department, phone, notification_preference
  - Password reset: reset_token, reset_token_expires (1-hour expiry)
  - Rate-limit tracking: login_attempt_count, login_lockout_until
"""

import enum
from datetime import datetime, timezone

from flask_login import UserMixin

from .base import db


class UserRole(enum.Enum):
    PLANNER = "PLANNER"
    MANAGER = "MANAGER"


class NotificationPreference(enum.Enum):
    EMAIL = "EMAIL"
    SMS = "SMS"
    NONE = "NONE"


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)

    # --- US-1: Authentication ---
    email = db.Column(db.String(254), unique=True, nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)           # bcrypt hash
    role = db.Column(db.Enum(UserRole), nullable=False)

    # Password reset (token expires in 1 hour per SRS)
    reset_token = db.Column(db.String(255), nullable=True)
    reset_token_expires = db.Column(db.DateTime(timezone=True), nullable=True)

    # Rate-limiting: max 5 attempts per 15 minutes
    login_attempt_count = db.Column(db.Integer, nullable=False, default=0)
    login_lockout_until = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- US-2: User Profile ---
    full_name = db.Column(db.String(255), nullable=True)
    department = db.Column(db.String(100), nullable=True)               # no special chars (enforced in form)
    phone = db.Column(db.String(10), nullable=True)                     # 10-digit format per SRS
    notification_preference = db.Column(
        db.Enum(NotificationPreference),
        nullable=False,
        default=NotificationPreference.NONE,
    )

    # --- Audit timestamps ---
    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    updated_at = db.Column(
        db.DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
    )

    # --- Relationships ---
    work_orders = db.relationship("WorkOrder", back_populates="planner", lazy="dynamic")
    notifications = db.relationship("Notification", back_populates="recipient", lazy="dynamic")
    audit_logs = db.relationship("AuditLog", back_populates="user", lazy="dynamic")

    def __repr__(self):
        return f"<User id={self.id} email={self.email} role={self.role.value}>"