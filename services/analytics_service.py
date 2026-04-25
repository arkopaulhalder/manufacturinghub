"""
services/analytics_service.py

US-9 — Production Analytics Dashboard data.

Provides aggregated metrics for:
  - Production volume by product (last 30 days) → bar chart
  - Machine utilization (scheduled hours vs available) → pie chart
  - Inventory turnover for top 5 materials → line chart
  - CSV export helpers for work orders and inventory movements

SRS Don'ts:
  - Do not expose sensitive cost data to production planners
    (routes enforce MANAGER-only access)
"""

import csv
import io
from datetime import datetime, timedelta, timezone
from decimal import Decimal

from sqlalchemy import func, case

from models.base import db
from models.inventory import InventoryMovement, MovementType
from models.machine import Machine, MachineStatus
from models.material import Material
from models.work_order import WorkOrder, WorkOrderMaterial, WorkOrderStatus


# ------------------------------------------------------------------ #
# Card KPIs                                                           #
# ------------------------------------------------------------------ #

def get_analytics_cards() -> dict:
    """Summary cards for the analytics dashboard header."""
    now = datetime.now(timezone.utc)
    thirty_days_ago = now - timedelta(days=30)

    active_work_orders = WorkOrder.query.filter(
        WorkOrder.status.in_([WorkOrderStatus.SCHEDULED, WorkOrderStatus.IN_PROGRESS])
    ).count()

    machines_in_maintenance = Machine.query.filter_by(
        status=MachineStatus.MAINTENANCE
    ).count()

    low_stock = Material.query.filter(
        Material.current_stock <= Material.reorder_level
    ).count()

    completed_30d = WorkOrder.query.filter(
        WorkOrder.status == WorkOrderStatus.COMPLETED,
        WorkOrder.updated_at >= thirty_days_ago,
    ).count()

    return {
        "active_work_orders": active_work_orders,
        "machines_in_maintenance": machines_in_maintenance,
        "materials_below_reorder": low_stock,
        "completed_30d": completed_30d,
    }


# ------------------------------------------------------------------ #
# Bar chart — Production volume by product (last 30 days)             #
# ------------------------------------------------------------------ #

def get_production_volume_by_product(days: int = 30) -> dict:
    """
    Completed work orders grouped by product_name.
    Returns {labels: [...], data: [...]}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    rows = (
        db.session.query(
            WorkOrder.product_name,
            func.sum(WorkOrder.quantity),
        )
        .filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.updated_at >= cutoff,
        )
        .group_by(WorkOrder.product_name)
        .order_by(func.sum(WorkOrder.quantity).desc())
        .limit(10)
        .all()
    )

    labels = [r[0] for r in rows]
    data = [float(r[1]) for r in rows]

    return {"labels": labels, "data": data}


# ------------------------------------------------------------------ #
# Pie chart — Machine utilization (hours used vs available)           #
# ------------------------------------------------------------------ #

def get_machine_utilization() -> dict:
    """
    For each machine: sum of estimated_hours from COMPLETED + IN_PROGRESS
    work orders as 'used'. Assume 8 hrs/day × 30 days as 'available'.

    Returns {labels: [...], used: [...], available: [...]}.
    """
    machines = Machine.query.order_by(Machine.machine_id).all()
    if not machines:
        return {"labels": [], "used": [], "available": []}

    cutoff = datetime.now(timezone.utc) - timedelta(days=30)
    available_hours_per_machine = 8 * 30  # 240 hrs per machine

    labels = []
    used = []
    available = []

    for machine in machines:
        total_hours = (
            db.session.query(func.coalesce(func.sum(WorkOrder.estimated_hours), 0))
            .filter(
                WorkOrder.machine_id == machine.id,
                WorkOrder.status.in_([
                    WorkOrderStatus.COMPLETED,
                    WorkOrderStatus.IN_PROGRESS,
                    WorkOrderStatus.SCHEDULED,
                ]),
                WorkOrder.updated_at >= cutoff,
            )
            .scalar()
        )

        hrs = float(total_hours)
        labels.append(machine.machine_id)
        used.append(round(hrs, 1))
        available.append(round(max(available_hours_per_machine - hrs, 0), 1))

    return {"labels": labels, "used": used, "available": available}


# ------------------------------------------------------------------ #
# Line chart — Inventory turnover for top 5 materials                 #
# ------------------------------------------------------------------ #

def get_inventory_turnover(days: int = 30, top_n: int = 5) -> dict:
    """
    Daily OUT movement quantities for the top N materials by total movement.
    Returns {labels: [date_strings], datasets: [{label, data}, ...]}.
    """
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)

    top_materials = (
        db.session.query(
            InventoryMovement.material_id,
            func.sum(InventoryMovement.qty).label("total"),
        )
        .filter(
            InventoryMovement.type == MovementType.OUT,
            InventoryMovement.timestamp >= cutoff,
        )
        .group_by(InventoryMovement.material_id)
        .order_by(func.sum(InventoryMovement.qty).desc())
        .limit(top_n)
        .all()
    )

    if not top_materials:
        date_labels = []
        today = datetime.now(timezone.utc).date()
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            date_labels.append(d.strftime("%d %b"))
        return {"labels": date_labels, "datasets": []}

    material_ids = [r[0] for r in top_materials]

    materials = {m.id: m for m in Material.query.filter(Material.id.in_(material_ids)).all()}

    today = datetime.now(timezone.utc).date()
    date_labels = []
    for i in range(days):
        d = today - timedelta(days=days - 1 - i)
        date_labels.append(d.strftime("%d %b"))

    datasets = []
    for mat_id in material_ids:
        mat = materials.get(mat_id)
        if not mat:
            continue

        daily_data = []
        for i in range(days):
            d = today - timedelta(days=days - 1 - i)
            day_start = datetime(d.year, d.month, d.day, tzinfo=timezone.utc)
            day_end = day_start + timedelta(days=1)

            total = (
                db.session.query(func.coalesce(func.sum(InventoryMovement.qty), 0))
                .filter(
                    InventoryMovement.material_id == mat_id,
                    InventoryMovement.type == MovementType.OUT,
                    InventoryMovement.timestamp >= day_start,
                    InventoryMovement.timestamp < day_end,
                )
                .scalar()
            )
            daily_data.append(float(total))

        datasets.append({
            "label": f"{mat.sku} ({mat.name})",
            "data": daily_data,
        })

    return {"labels": date_labels, "datasets": datasets}


# ------------------------------------------------------------------ #
# CSV Export — Work orders                                            #
# ------------------------------------------------------------------ #

def export_work_orders_csv() -> str:
    """Export all work orders as CSV string."""
    orders = (
        WorkOrder.query
        .order_by(WorkOrder.created_at.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Order ID", "Product", "Quantity", "Priority", "Status",
        "Machine", "Target Date", "Scheduled Start", "Scheduled End",
        "Est. Hours", "Created At",
    ])

    for wo in orders:
        writer.writerow([
            f"WO-{wo.id:04d}",
            wo.product_name,
            float(wo.quantity),
            wo.priority.value,
            wo.status.value,
            wo.machine.machine_id if wo.machine else "",
            wo.target_completion_date.strftime("%Y-%m-%d") if wo.target_completion_date else "",
            wo.scheduled_start.strftime("%Y-%m-%d %H:%M") if wo.scheduled_start else "",
            wo.scheduled_end.strftime("%Y-%m-%d %H:%M") if wo.scheduled_end else "",
            float(wo.estimated_hours) if wo.estimated_hours else "",
            wo.created_at.strftime("%Y-%m-%d %H:%M"),
        ])

    return output.getvalue()


# ------------------------------------------------------------------ #
# CSV Export — Inventory movements                                    #
# ------------------------------------------------------------------ #

def export_inventory_movements_csv() -> str:
    """Export all inventory movements as CSV string."""
    movements = (
        InventoryMovement.query
        .order_by(InventoryMovement.timestamp.desc())
        .all()
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "ID", "Material SKU", "Material Name", "Type", "Quantity",
        "Work Order", "Supplier", "Reason", "Delta", "Timestamp",
    ])

    for mv in movements:
        writer.writerow([
            mv.id,
            mv.material.sku if mv.material else "",
            mv.material.name if mv.material else "",
            mv.type.value,
            float(mv.qty),
            f"WO-{mv.work_order_id:04d}" if mv.work_order_id else "",
            mv.supplier or "",
            mv.reason or "",
            float(mv.qty_delta) if mv.qty_delta else "",
            mv.timestamp.strftime("%Y-%m-%d %H:%M"),
        ])

    return output.getvalue()
