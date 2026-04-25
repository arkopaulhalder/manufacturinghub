import json
from datetime import datetime, timezone

from flask import Response, render_template, redirect, url_for
from flask_login import current_user, login_required

from decorators.rbac import requires_role
from models import UserRole
from services.dashboard_service import (
    get_manager_low_stock_preview,
    get_manager_stats,
    get_manager_upcoming_maintenance,
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
    upcoming_maintenance = get_manager_upcoming_maintenance(limit=5)
    return render_template(
        "dashboard/manager.html",
        title="Manager Dashboard",
        stats=stats,
        low_stock_preview=low_stock_preview,
        upcoming_maintenance=upcoming_maintenance,
        now_utc=datetime.now(timezone.utc),
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


# ------------------------------------------------------------------ #
# US-9 — Production Analytics Dashboard (Manager only)                #
# ------------------------------------------------------------------ #

@dashboard_bp.route("/analytics")
@login_required
@requires_role("MANAGER")
def analytics():
    from services.analytics_service import (
        get_analytics_cards,
        get_inventory_turnover,
        get_machine_utilization,
        get_production_volume_by_product,
    )

    cards = get_analytics_cards()
    production_volume = get_production_volume_by_product(days=30)
    machine_util = get_machine_utilization()
    inventory_turnover = get_inventory_turnover(days=30, top_n=5)

    return render_template(
        "dashboard/analytics.html",
        cards=cards,
        production_volume_json=json.dumps(production_volume),
        machine_util_json=json.dumps(machine_util),
        inventory_turnover_json=json.dumps(inventory_turnover),
    )


@dashboard_bp.route("/analytics/export/work-orders")
@login_required
@requires_role("MANAGER")
def export_work_orders():
    from services.analytics_service import export_work_orders_csv
    csv_data = export_work_orders_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=work_orders.csv"
        },
    )


@dashboard_bp.route("/analytics/export/inventory")
@login_required
@requires_role("MANAGER")
def export_inventory():
    from services.analytics_service import export_inventory_movements_csv
    csv_data = export_inventory_movements_csv()
    return Response(
        csv_data,
        mimetype="text/csv",
        headers={
            "Content-Disposition": "attachment; filename=inventory_movements.csv"
        },
    )