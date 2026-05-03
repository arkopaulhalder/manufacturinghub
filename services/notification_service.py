"""
services/notification_service.py

US-8 — Notifications & Alerts business logic.

SRS acceptance criteria covered:
  - Low Stock Alert: daily cron checks current_stock ≤ reorder_level; enqueue to manager
  - Maintenance Alert: daily cron checks next_due_date within 3 days; enqueue to manager
  - Order Status Change: notify planner on SCHEDULED → IN_PROGRESS → COMPLETED
  - Outbox table: type, recipient_id, status [QUEUED/SENT/FAILED], payload JSON
  - Template emails with actionable links
  - Retry failed notifications up to 3 times

SRS Don'ts:
  - Do not block web requests on notification sending; use async worker
"""

from datetime import datetime, timedelta, timezone

from flask import current_app, url_for

from models.base import db
from models.material import Material
from models.maintenance import MaintenanceRule
from models.notification import Notification, NotificationStatus, NotificationType
from models.user import NotificationPreference, User, UserRole

MAX_RETRIES = 3
EMAIL_ADDRESS=["manager1@factory.com","manager2@factory.com"]

# ------------------------------------------------------------------ #
# Read — Notification inbox                                           #
# ------------------------------------------------------------------ #

def get_notifications_for_user(user_id: int, limit: int = 50) -> list[Notification]:
    """Return recent notifications for a user, newest first."""
    return (
        Notification.query
        .filter_by(recipient_id=user_id)
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


def get_unread_count(user_id: int) -> int:
    """Count queued (unread) notifications for a user."""
    return (
        Notification.query
        .filter_by(recipient_id=user_id, status=NotificationStatus.QUEUED)
        .count()
    )


def get_all_notifications(limit: int = 100) -> list[Notification]:
    """Admin view — all notifications across users."""
    return (
        Notification.query
        .order_by(Notification.created_at.desc())
        .limit(limit)
        .all()
    )


# ------------------------------------------------------------------ #
# Mark as read                                                        #
# ------------------------------------------------------------------ #

def mark_as_read(notification_id: int, user_id: int) -> tuple[bool, str]:
    """Mark a single notification as SENT (read)."""
    notif = db.session.get(Notification, notification_id)
    if not notif:
        return False, "Notification not found."
    if notif.recipient_id != user_id:
        return False, "Not your notification."
    if notif.status == NotificationStatus.QUEUED:
        notif.status = NotificationStatus.SENT
        notif.sent_at = datetime.now(timezone.utc)
        db.session.commit()
    return True, "Marked as read."


def mark_all_as_read(user_id: int) -> int:
    """Mark all QUEUED notifications for a user as SENT. Returns count."""
    now = datetime.now(timezone.utc)
    count = (
        Notification.query
        .filter_by(recipient_id=user_id, status=NotificationStatus.QUEUED)
        .update({
            Notification.status: NotificationStatus.SENT,
            Notification.sent_at: now,
        })
    )
    db.session.commit()
    return count


# ------------------------------------------------------------------ #
# Enqueue — create notification rows                                  #
# ------------------------------------------------------------------ #

def _get_managers() -> list[User]:
    """Return all manager users."""
    return User.query.filter_by(role=UserRole.MANAGER).all()


def enqueue_notification(
    notification_type: NotificationType,
    recipient: User,
    payload: dict,
) -> Notification:
    """Create a QUEUED notification row in the outbox."""
    notif = Notification(
        type=notification_type,
        recipient_id=recipient.id,
        status=NotificationStatus.QUEUED,
        payload=payload,
    )
    db.session.add(notif)
    return notif


def enqueue_low_stock_alert(material: Material) -> list[Notification]:
    """
    Enqueue LOW_STOCK notification to all managers for a material
    whose current_stock ≤ reorder_level.
    """
    managers = _get_managers()
    notifications = []
    for manager in managers:
        payload = {
            "title": f"Low Stock: {material.sku}",
            "message": (
                f"{material.name} ({material.sku}) stock is at "
                f"{float(material.current_stock)} {material.unit.value}, "
                f"below reorder level of {float(material.reorder_level)} {material.unit.value}."
            ),
            "material_id": material.id,
            "sku": material.sku,
            "current_stock": float(material.current_stock),
            "reorder_level": float(material.reorder_level),
            "action_label": f"Restock {material.sku}",
        }
        notif = enqueue_notification(NotificationType.LOW_STOCK, manager, payload)
        notifications.append(notif)
    return notifications


def enqueue_maintenance_due_alert(rule: MaintenanceRule) -> list[Notification]:
    """
    Enqueue MAINTENANCE_DUE notification to all managers for a
    machine with maintenance due within 3 days.
    """
    managers = _get_managers()
    notifications = []
    for manager in managers:
        payload = {
            "title": f"Maintenance Due: {rule.machine.machine_id}",
            "message": (
                f"Machine {rule.machine.machine_id} ({rule.machine.name}) "
                f"has maintenance due on {rule.next_due_date.strftime('%d %b %Y')}."
            ),
            "machine_id": rule.machine_id,
            "machine_code": rule.machine.machine_id,
            "rule_id": rule.id,
            "next_due_date": rule.next_due_date.isoformat(),
            "action_label": "View Maintenance",
        }
        notif = enqueue_notification(NotificationType.MAINTENANCE_DUE, manager, payload)
        notifications.append(notif)
    return notifications


def enqueue_order_status_notification(
    work_order,
    old_status: str,
    new_status: str,
) -> Notification | None:
    """
    Enqueue ORDER_STATUS notification to the planner who owns the work order
    when status changes (SCHEDULED → IN_PROGRESS → COMPLETED).
    """
    planner = work_order.planner
    payload = {
        "title": f"WO-{work_order.id:04d} is now {new_status}",
        "message": (
            f"Work order WO-{work_order.id:04d} ({work_order.product_name}) "
            f"status changed from {old_status} to {new_status}."
        ),
        "work_order_id": work_order.id,
        "product_name": work_order.product_name,
        "old_status": old_status,
        "new_status": new_status,
        "action_label": f"View WO-{work_order.id:04d}",
    }
    notif = enqueue_notification(NotificationType.ORDER_STATUS, planner, payload)
    return notif


# ------------------------------------------------------------------ #
# Daily cron jobs — scan & enqueue                                    #
# ------------------------------------------------------------------ #

def run_low_stock_check() -> int:
    """
    Daily cron: scan all materials where current_stock ≤ reorder_level
    and enqueue LOW_STOCK notifications to managers.
    Returns count of notifications created.
    """
    low_stock_materials = (
        Material.query
        .filter(Material.current_stock <= Material.reorder_level)
        .all()
    )

    count = 0
    for material in low_stock_materials:
        notifications = enqueue_low_stock_alert(material)
        count += len(notifications)

    if count > 0:
        db.session.commit()
    return count


def run_maintenance_due_check() -> int:
    """
    Daily cron: scan all maintenance rules where next_due_date is within
    3 days (or overdue) and enqueue MAINTENANCE_DUE notifications.
    Returns count of notifications created.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=3)

    due_rules = (
        MaintenanceRule.query
        .filter(
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date <= horizon,
        )
        .all()
    )

    count = 0
    for rule in due_rules:
        notifications = enqueue_maintenance_due_alert(rule)
        count += len(notifications)

    if count > 0:
        db.session.commit()
    return count


# ------------------------------------------------------------------ #
# Process queue — send notifications (async worker)                   #
# ------------------------------------------------------------------ #

def _build_email_body(notification: Notification) -> str:
    """Build email body with actionable link from payload."""
    payload = notification.payload
    body = f"{payload.get('message', '')}\n\n"

    action_label = payload.get("action_label", "")
    if action_label:
        body += f"Action: {action_label}\n"

    body += (
        "\n—\n"
        "ManufacturingHub Notifications\n"
        "This is an automated notification."
    )
    return body


def _send_email_notification(notification: Notification) -> bool:
    """
    Send an email notification using Flask-Mail.
    Returns True on success, False on failure.
    """
    from app import mail
    from flask_mail import Message

    recipient = notification.recipient
    if recipient.notification_preference != NotificationPreference.EMAIL:
        return True

    if not recipient.email:
        return False

    try:
        from email_validator import validate_email, EmailNotValidError
    except ImportError:
        validate_email = None

    if validate_email:
        try:
            # Check if email is valid before attempting to send
            validate_email(recipient.email, check_deliverability=False)

            if recipient.email in EMAIL_ADDRESS :
                raise EmailNotValidError("Invalid email address")
        except EmailNotValidError as e:
            current_app.logger.warning(
                "Skipping invalid email address %s (notification %d): %s",
                recipient.email, notification.id, str(e)
            )
            return False

    payload = notification.payload
    subject = f"ManufacturingHub — {payload.get('title', 'Notification')}"
    body = _build_email_body(notification)

    msg = Message(
        subject=subject,
        recipients=[recipient.email],
        body=body,
    )

    try:
        mail.send(msg)
        current_app.logger.info(f"Successfully sent email notification to: {recipient.email}")
        return True
    except Exception as exc:
        current_app.logger.warning(
            "Failed to send email to %s (notification %d): %s",
            recipient.email, notification.id, exc
        )
        return False


def process_notification_queue(batch_size: int = 50) -> dict:
    """
    Process queued notifications: attempt to send, update status.
    Retries failed notifications up to MAX_RETRIES times.

    Returns dict with counts: sent, failed, skipped.

    SRS Don'ts: This should run in a background worker, not in
    the web request cycle.
    """
    queued = (
        Notification.query
        .filter_by(status=NotificationStatus.QUEUED)
        .order_by(Notification.created_at.asc())
        .limit(batch_size)
        .all()
    )

    failed = (
        Notification.query
        .filter(
            Notification.status == NotificationStatus.FAILED,
            Notification.retry_count < MAX_RETRIES,
        )
        .order_by(Notification.created_at.asc())
        .limit(batch_size)
        .all()
    )

    to_process = queued + failed
    stats = {"sent": 0, "failed": 0, "skipped": 0}

    for notif in to_process:
        recipient = notif.recipient

        if recipient.notification_preference == NotificationPreference.NONE:
            notif.status = NotificationStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            stats["skipped"] += 1
            continue

        if recipient.notification_preference == NotificationPreference.SMS:
            notif.status = NotificationStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            stats["skipped"] += 1
            continue

        success = _send_email_notification(notif) # only for email else skip for SMS and None
        if success: 
            notif.status = NotificationStatus.SENT
            notif.sent_at = datetime.now(timezone.utc)
            stats["sent"] += 1
        else:
            notif.retry_count += 1
            if notif.retry_count >= MAX_RETRIES:
                notif.status = NotificationStatus.FAILED
            stats["failed"] += 1

    db.session.commit()
    return stats
