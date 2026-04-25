"""
Dashboard KPIs and short lists for Planner / Manager home views.
"""

from datetime import datetime, timedelta, timezone

from models.machine import Machine, MachineStatus
from models.maintenance import MaintenanceRule, MaintenanceFrequency
from models.material import Material
from models.work_order import WorkOrder, WorkOrderStatus


def _start_of_utc_day() -> datetime:
    now = datetime.now(timezone.utc)
    return now.replace(hour=0, minute=0, second=0, microsecond=0)


def get_planner_stats(planner_id: int) -> dict:
    """
    Work order counts for a single planner.
    completed_today: COMPLETED with updated_at on current UTC calendar day.
    """
    base = WorkOrder.query.filter_by(planner_id=planner_id)

    def count_status(st: WorkOrderStatus) -> int:
        return base.filter(WorkOrder.status == st).count()

    start_day = _start_of_utc_day()
    completed_today = (
        base.filter(
            WorkOrder.status == WorkOrderStatus.COMPLETED,
            WorkOrder.updated_at >= start_day,
        ).count()
    )

    return {
        "pending": count_status(WorkOrderStatus.PENDING),
        "scheduled": count_status(WorkOrderStatus.SCHEDULED),
        "in_progress": count_status(WorkOrderStatus.IN_PROGRESS),
        "completed_today": completed_today,
    }


def get_planner_recent_orders(planner_id: int, limit: int = 5) -> list[WorkOrder]:
    return (
        WorkOrder.query.filter_by(planner_id=planner_id)
        .order_by(WorkOrder.created_at.desc())
        .limit(limit)
        .all()
    )


def get_manager_stats() -> dict:
    """Shop-floor snapshot for plant manager dashboard."""
    active_machines = Machine.query.filter_by(status=MachineStatus.ACTIVE).count()

    open_work_orders = WorkOrder.query.filter(
        WorkOrder.status != WorkOrderStatus.COMPLETED
    ).count()

    low_stock = Material.query.filter(Material.current_stock <= Material.reorder_level).count()

    # Maintenance due: next_due_date within the next 7 days (or already overdue)
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=7)
    maintenance_due = (
        MaintenanceRule.query.filter(
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date <= horizon,
        ).count()
    )

    return {
        "active_machines": active_machines,
        "open_work_orders": open_work_orders,
        "low_stock_items": low_stock,
        "maintenance_due": maintenance_due,
    }


def get_manager_low_stock_preview(limit: int = 3) -> list[Material]:
    """Top low-stock materials by smallest headroom (stock - reorder), most critical first."""
    return (
        Material.query.filter(Material.current_stock <= Material.reorder_level)
        .order_by(
            (Material.current_stock - Material.reorder_level).asc(),
            Material.sku.asc(),
        )
        .limit(limit)
        .all()
    )


def get_manager_upcoming_maintenance(limit: int = 5) -> list[MaintenanceRule]:
    """
    US-7: Return maintenance rules due within next 7 days (or overdue).
    Sorted by next_due_date ascending (most urgent first).
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=7)
    return (
        MaintenanceRule.query
        .filter(
            MaintenanceRule.next_due_date.isnot(None),
            MaintenanceRule.next_due_date <= horizon,
        )
        .order_by(MaintenanceRule.next_due_date.asc())
        .limit(limit)
        .all()
    )
