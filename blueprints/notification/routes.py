"""
blueprints/notification/routes.py — US-8 Notification inbox.

Routes:
  GET  /notifications/             — View all notifications for current user
  POST /notifications/<id>/read    — Mark a single notification as read
  POST /notifications/read-all     — Mark all notifications as read
"""

from flask import flash, redirect, render_template, url_for
from flask_login import current_user, login_required

from services.notification_service import (
    get_notifications_for_user,
    get_unread_count,
    mark_all_as_read,
    mark_as_read,
)
from . import notification_bp


@notification_bp.route("/")
@login_required
def inbox():
    """Show all notifications for the current user."""
    notifications = get_notifications_for_user(current_user.id)
    unread = get_unread_count(current_user.id)
    return render_template(
        "notification/inbox.html",
        notifications=notifications,
        unread_count=unread,
    )


@notification_bp.route("/<int:notif_id>/read", methods=["POST"])
@login_required
def read(notif_id):
    """Mark a single notification as read."""
    success, message = mark_as_read(notif_id, current_user.id)
    if not success:
        flash(message, "danger")
    return redirect(url_for("notification.inbox"))


@notification_bp.route("/read-all", methods=["POST"])
@login_required
def read_all():
    """Mark all notifications as read."""
    count = mark_all_as_read(current_user.id)
    if count > 0:
        flash(f"{count} notification(s) marked as read.", "success")
    return redirect(url_for("notification.inbox"))
