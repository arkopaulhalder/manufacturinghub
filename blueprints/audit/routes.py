"""
blueprints/audit/routes.py — US-10 Audit log viewer.

SRS RBAC: Manager only.

Routes:
  GET /audit/          — View audit log (paginated)
"""

from flask import render_template, request
from flask_login import login_required

from decorators.rbac import requires_role
from services.audit_service import get_audit_logs, get_audit_logs_count
from . import audit_bp


@audit_bp.route("/")
@login_required
@requires_role("MANAGER")
def log_list():
    """Paginated audit log viewer."""
    page = request.args.get("page", 1, type=int)
    per_page = 30
    offset = (page - 1) * per_page

    total = get_audit_logs_count()
    logs = get_audit_logs(limit=per_page, offset=offset)
    total_pages = max(1, (total + per_page - 1) // per_page)

    return render_template(
        "audit/list.html",
        logs=logs,
        page=page,
        total_pages=total_pages,
        total=total,
    )
