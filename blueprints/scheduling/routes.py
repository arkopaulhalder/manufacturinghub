"""
blueprints/scheduling/routes.py — US-5 Production Scheduling.

SRS RBAC:
  - Schedule / Unschedule: PLANNER (own PENDING orders)
  - Gantt view: PLANNER + MANAGER

Routes:
  GET  /schedule/                  — Gantt view (all scheduled + in-progress)
  GET  /schedule/<wo_id>           — Schedule form for a specific work order
  POST /schedule/<wo_id>           — Submit schedule assignment
  POST /schedule/<wo_id>/unschedule — Remove assignment, revert to PENDING
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from decorators.rbac import requires_role
from services.scheduling_service import (
    get_available_machines,
    get_machine_schedule,
    get_scheduled_orders_for_gantt,
    schedule_work_order,
    unschedule_work_order,
    calculate_estimated_hours,
    start_work_order,
    complete_work_order,
)
from services.work_order_service import (
    check_material_availability,
    get_work_order_by_id,
)
from models.work_order import WorkOrderStatus

from . import scheduling_bp
from .forms import ScheduleForm


# ------------------------------------------------------------------ #
# Gantt view — all scheduled + in-progress orders                    #
# ------------------------------------------------------------------ #

@scheduling_bp.route("/")
@login_required
def gantt():
    orders = get_scheduled_orders_for_gantt()
    return render_template("scheduling/gantt.html", orders=orders)


# ------------------------------------------------------------------ #
# Schedule a work order (Planner only)                               #
# ------------------------------------------------------------------ #

@scheduling_bp.route("/<int:wo_id>", methods=["GET", "POST"])
@login_required
@requires_role("PLANNER")
def schedule(wo_id):
    wo = get_work_order_by_id(wo_id)
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("work_order.list"))

    if wo.planner_id != current_user.id:
        flash("You can only schedule your own work orders.", "danger")
        return redirect(url_for("work_order.list"))

    if wo.status != WorkOrderStatus.PENDING:
        flash("Only PENDING work orders can be scheduled.", "warning")
        return redirect(url_for("work_order.detail", wo_id=wo_id))

    # Populate machine choices — ACTIVE only per SRS
    machines = get_available_machines()
    if not machines:
        flash("No active machines available for scheduling.", "warning")
        return redirect(url_for("work_order.detail", wo_id=wo_id))

    form = ScheduleForm()
    form.machine_id.choices = [
        (m.id, f"{m.machine_id} — {m.name} ({m.capacity_per_hour} units/hr)")
        for m in machines
    ]

    # Material availability warnings — shown but do not block scheduling
    bom_lines = [
        {"material_id": m.material_id, "required_qty": float(m.required_qty)}
        for m in wo.materials
    ]
    warnings = check_material_availability(bom_lines)

    # Preview: estimated hours for selected machine on GET
    preview = None
    if request.method == "GET" and machines:
        first_machine = machines[0]
        est = calculate_estimated_hours(
            float(wo.quantity), float(first_machine.capacity_per_hour)
        )
        preview = {"machine": first_machine, "estimated_hours": est}

    if form.validate_on_submit():
        success, message = schedule_work_order(
            wo_id=wo_id,
            machine_pk=form.machine_id.data,
            scheduled_start=form.scheduled_start.data,
            requesting_planner_id=current_user.id,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("work_order.detail", wo_id=wo_id))

    # Pass existing schedule for chosen machine to show on page
    machine_schedules = {
        m.id: get_machine_schedule(m.id) for m in machines
    }

    return render_template(
        "scheduling/schedule_form.html",
        form=form,
        wo=wo,
        machines=machines,
        warnings=warnings,
        preview=preview,
        machine_schedules=machine_schedules,
    )


# ------------------------------------------------------------------ #
# Unschedule (Planner only)                                          #
# ------------------------------------------------------------------ #

@scheduling_bp.route("/<int:wo_id>/unschedule", methods=["POST"])
@login_required
@requires_role("PLANNER")
def unschedule(wo_id):
    success, message = unschedule_work_order(wo_id, current_user.id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("work_order.detail", wo_id=wo_id))


# ------------------------------------------------------------------ #
# US-6 — Start work order (SCHEDULED → IN_PROGRESS, consume materials)#
# ------------------------------------------------------------------ #

@scheduling_bp.route("/<int:wo_id>/start", methods=["POST"])
@login_required
@requires_role("PLANNER")
def start(wo_id):
    """
    Start a SCHEDULED work order — transitions to IN_PROGRESS
    and consumes all BOM materials from inventory.
    """
    success, message, alerts = start_work_order(wo_id, current_user.id)

    if success:
        flash(message, "success")
        if alerts:
            for alert in alerts:
                flash(
                    f"Low stock alert: {alert['sku']} ({alert['name']}) — "
                    f"Stock: {alert['current_stock']} {alert['unit']}, "
                    f"Reorder level: {alert['reorder_level']} {alert['unit']}",
                    "warning"
                )
    else:
        flash(message, "danger")

    return redirect(url_for("work_order.detail", wo_id=wo_id))


# ------------------------------------------------------------------ #
# US-6 — Complete work order (IN_PROGRESS → COMPLETED)                #
# ------------------------------------------------------------------ #

@scheduling_bp.route("/<int:wo_id>/complete", methods=["POST"])
@login_required
@requires_role("PLANNER")
def complete(wo_id):
    """Mark an IN_PROGRESS work order as COMPLETED."""
    success, message = complete_work_order(wo_id, current_user.id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("work_order.detail", wo_id=wo_id))