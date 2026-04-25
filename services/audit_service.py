"""
services/audit_service.py

US-10 — Security & Audit logging.

Central helper for writing audit trail entries.

SRS acceptance criteria:
  - Log IP address, user_id, action, timestamp, old/new values
  - Audit: work order creation/updates, inventory adjustments,
    maintenance logs, user logins

SRS Don'ts:
  - Do not log passwords or tokens
"""

from datetime import datetime, timezone

from models.audit import AuditAction, AuditLog
from models.base import db


def log_audit(
    action: AuditAction,
    user_id: int | None = None,
    ip_address: str | None = None,
    entity_type: str | None = None,
    entity_id: int | None = None,
    old_values: dict | None = None,
    new_values: dict | None = None,
) -> AuditLog:
    """
    Central audit logger. Creates an AuditLog row.

    SRS Don'ts: callers must NEVER pass password_hash, tokens,
    or other secrets in old_values / new_values.
    """
    entry = AuditLog(
        user_id=user_id,
        action=action,
        ip_address=ip_address,
        entity_type=entity_type,
        entity_id=entity_id,
        old_values=old_values,
        new_values=new_values,
        timestamp=datetime.now(timezone.utc),
    )
    db.session.add(entry)
    return entry


def get_audit_logs(limit: int = 100, offset: int = 0) -> list[AuditLog]:
    """Return recent audit logs, newest first."""
    return (
        AuditLog.query
        .order_by(AuditLog.timestamp.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


def get_audit_logs_count() -> int:
    """Total number of audit log entries."""
    return AuditLog.query.count()


def get_audit_logs_for_entity(
    entity_type: str, entity_id: int, limit: int = 50
) -> list[AuditLog]:
    """Return audit logs for a specific entity."""
    return (
        AuditLog.query
        .filter_by(entity_type=entity_type, entity_id=entity_id)
        .order_by(AuditLog.timestamp.desc())
        .limit(limit)
        .all()
    )
