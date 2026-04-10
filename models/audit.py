"""
AuditLog model — covers US-10 (Security & Audit).

Captures key actions per SRS acceptance criteria:
  work order creation/updates, inventory adjustments,
  maintenance logs, user logins.

Per SRS Dos:
  Log IP address, user_id, action, timestamp, old/new values for audited entities.

Per SRS Don'ts:
  Do NOT log passwords or tokens (enforced at service layer).
"""

import enum
from datetime import datetime, timezone

from .base import db


class AuditAction(enum.Enum):
    USER_LOGIN = "USER_LOGIN"
    USER_PROFILE_UPDATE = "USER_PROFILE_UPDATE"
    WORK_ORDER_CREATE = "WORK_ORDER_CREATE"
    WORK_ORDER_UPDATE = "WORK_ORDER_UPDATE"
    INVENTORY_ADJUST = "INVENTORY_ADJUST"
    MAINTENANCE_LOG = "MAINTENANCE_LOG"


class AuditLog(db.Model):
    __tablename__ = "audit_logs"

    id = db.Column(db.Integer, primary_key=True)

    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=True, index=True   # nullable: system actions
    )
    action = db.Column(db.Enum(AuditAction), nullable=False, index=True)
    ip_address = db.Column(db.String(45), nullable=True)                   # supports IPv6
    entity_type = db.Column(db.String(100), nullable=True)                 # e.g. "WorkOrder", "Material"
    entity_id = db.Column(db.Integer, nullable=True)

    # old_values / new_values store the before/after state as JSON
    old_values = db.Column(db.JSON, nullable=True)
    new_values = db.Column(db.JSON, nullable=True)

    timestamp = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc), index=True
    )

    # --- Relationships ---
    user = db.relationship("User", back_populates="audit_logs")

    def __repr__(self):
        return f"<AuditLog id={self.id} action={self.action.value} user_id={self.user_id}>"