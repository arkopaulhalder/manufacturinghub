from flask import render_template, redirect, url_for
from flask_login import current_user, login_required

from decorators.rbac import requires_role
from models import UserRole
from services.dashboard_service import (
    get_manager_low_stock_preview,
    get_manager_stats,
    get_planner_recent_orders,
    get_planner_stats,
)

from . import dashboard_bp


@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == UserRole.MANAGER:
        return redirect(url_for("dashboard.manager"))
    return redirect(url_for("dashboard.planner"))


@dashboard_bp.route("/manager")
@login_required
@requires_role("MANAGER")
def manager():
    stats = get_manager_stats()
    low_stock_preview = get_manager_low_stock_preview(limit=3)
    return render_template(
        "dashboard/manager.html",
        title="Manager Dashboard",
        stats=stats,
        low_stock_preview=low_stock_preview,
    )


@dashboard_bp.route("/planner")
@login_required
@requires_role("PLANNER")
def planner():
    stats = get_planner_stats(current_user.id)
    recent_orders = get_planner_recent_orders(current_user.id, limit=5)
    return render_template(
        "dashboard/planner.html",
        stats=stats,
        recent_orders=recent_orders,
    )