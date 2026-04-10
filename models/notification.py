"""
Notification model — covers US-8 (Notifications & Alerts).

Implements the outbox pattern per SRS:
  Outbox table tracks (type, recipient_id, status [QUEUED/SENT/FAILED], payload JSON)

Notification types from SRS:
  LOW_STOCK       — daily cron fires when current_stock ≤ reorder_level
  MAINTENANCE_DUE — daily cron fires when next_due_date within 3 days
  ORDER_STATUS    — fired when work order status changes (SCHEDULED → IN_PROGRESS → COMPLETED)

Retry logic: up to 3 attempts (retry_count tracked here).
Async worker must process this table — do not block web requests.
"""

import enum
from datetime import datetime, timezone

from .base import db


class NotificationType(enum.Enum):
    LOW_STOCK = "LOW_STOCK"
    MAINTENANCE_DUE = "MAINTENANCE_DUE"
    ORDER_STATUS = "ORDER_STATUS"


class NotificationStatus(enum.Enum):
    QUEUED = "QUEUED"
    SENT = "SENT"
    FAILED = "FAILED"


class Notification(db.Model):
    __tablename__ = "notifications"

    id = db.Column(db.Integer, primary_key=True)

    type = db.Column(db.Enum(NotificationType), nullable=False)
    recipient_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    status = db.Column(db.Enum(NotificationStatus), nullable=False, default=NotificationStatus.QUEUED, index=True)

    # JSON payload: contains context-specific data (material name, order id, machine name, etc.)
    payload = db.Column(db.JSON, nullable=False)

    # Retry tracking — max 3 attempts per SRS
    retry_count = db.Column(db.Integer, nullable=False, default=0)

    created_at = db.Column(
        db.DateTime(timezone=True), nullable=False, default=lambda: datetime.now(timezone.utc)
    )
    sent_at = db.Column(db.DateTime(timezone=True), nullable=True)

    # --- Relationships ---
    recipient = db.relationship("User", back_populates="notifications")

    def __repr__(self):
        return f"<Notification id={self.id} type={self.type.value} status={self.status.value}>"