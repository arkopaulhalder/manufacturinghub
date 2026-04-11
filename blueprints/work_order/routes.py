"""
blueprints/work_order/routes.py — US-4 Work Order Creation.

SRS RBAC:
  - Create / Edit / Delete: PLANNER only (own orders)
  - List / Detail: PLANNER (own) + MANAGER (all)

BOM lines come from the form as repeating hidden fields:
  material_id_0, required_qty_0, material_id_1, required_qty_1 ...
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from decorators.rbac import requires_role
from models.material import Material
from models.user import UserRole
from services.work_order_service import (
    check_material_availability,
    create_work_order,
    delete_work_order,
    get_all_work_orders,
    get_work_order_by_id,
    get_work_orders_for_planner,
    update_work_order,
)
from . import work_order_bp
from .forms import WorkOrderForm


# ------------------------------------------------------------------ #
# Helper — parse BOM lines from request.form                         #
# ------------------------------------------------------------------ #

def _parse_bom_lines(form_data) -> list[dict]:
    """
    Extract repeating BOM line fields from POST data.
    Expects:  material_id_0, required_qty_0,
              material_id_1, required_qty_1, ...
    """
    lines = []
    i = 0
    while True:
        mat_id = form_data.get(f"material_id_{i}")
        req_qty = form_data.get(f"required_qty_{i}")
        if mat_id is None:
            break
        if mat_id.strip() and req_qty.strip():
            lines.append({
                "material_id": mat_id.strip(),
                "required_qty": req_qty.strip(),
            })
        i += 1
    return lines


# ------------------------------------------------------------------ #
# List                                                                #
# ------------------------------------------------------------------ #

@work_order_bp.route("/")
@login_required
def list():
    if current_user.role == UserRole.MANAGER:
        orders = get_all_work_orders()
    else:
        orders = get_work_orders_for_planner(current_user.id)
    return render_template("work_order/list.html", orders=orders)


# ------------------------------------------------------------------ #
# Detail                                                              #
# ------------------------------------------------------------------ #

@work_order_bp.route("/<int:wo_id>")
@login_required
def detail(wo_id):
    wo = get_work_order_by_id(wo_id)
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("work_order.list"))

    # Planner can only see their own orders
    if current_user.role == UserRole.PLANNER and wo.planner_id != current_user.id:
        flash("Not authorised to view this work order.", "danger")
        return redirect(url_for("work_order.list"))

    # Check material availability warnings for this order
    bom_lines = [
        {"material_id": m.material_id, "required_qty": float(m.required_qty)}
        for m in wo.materials
    ]
    warnings = check_material_availability(bom_lines)
    return render_template("work_order/detail.html", wo=wo, warnings=warnings)


# ------------------------------------------------------------------ #
# Create (Planner only)                                               #
# ------------------------------------------------------------------ #

@work_order_bp.route("/new", methods=["GET", "POST"])
@login_required
@requires_role("PLANNER")
def create():
    form = WorkOrderForm()
    materials = Material.query.order_by(Material.name).all()
    warnings = []

    if form.validate_on_submit():
        bom_lines = _parse_bom_lines(request.form)

        # Show stock warnings before saving — SRS Dos
        warnings = check_material_availability(bom_lines)

        success, message, wo = create_work_order(
            product_name=form.product_name.data,
            quantity=form.quantity.data,
            priority_str=form.priority.data,
            target_completion_date=form.target_completion_date.data,
            planner_id=current_user.id,
            bom_lines=bom_lines,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("work_order.detail", wo_id=wo.id))

    return render_template(
        "work_order/form.html",
        form=form,
        materials=materials,
        warnings=warnings,
        title="Create Work Order",
        bom_lines=[],
    )


# ------------------------------------------------------------------ #
# Edit (Planner, own PENDING orders only)                            #
# ------------------------------------------------------------------ #

@work_order_bp.route("/<int:wo_id>/edit", methods=["GET", "POST"])
@login_required
@requires_role("PLANNER")
def edit(wo_id):
    wo = get_work_order_by_id(wo_id)
    if not wo:
        flash("Work order not found.", "danger")
        return redirect(url_for("work_order.list"))

    if wo.planner_id != current_user.id:
        flash("You can only edit your own work orders.", "danger")
        return redirect(url_for("work_order.list"))

    from models.work_order import WorkOrderStatus
    if wo.status != WorkOrderStatus.PENDING:
        flash("Only PENDING work orders can be edited.", "warning")
        return redirect(url_for("work_order.detail", wo_id=wo_id))

    materials = Material.query.order_by(Material.name).all()
    warnings = []

    form = WorkOrderForm(obj=wo)

    if request.method == "GET":
        form.priority.data = wo.priority.value
        existing_bom = [
            {"material_id": str(m.material_id), "required_qty": str(m.required_qty)}
            for m in wo.materials
        ]
    else:
        existing_bom = _parse_bom_lines(request.form)

    if form.validate_on_submit():
        bom_lines = _parse_bom_lines(request.form)
        warnings = check_material_availability(bom_lines)

        success, message = update_work_order(
            wo_id=wo_id,
            requesting_planner_id=current_user.id,
            product_name=form.product_name.data,
            quantity=form.quantity.data,
            priority_str=form.priority.data,
            target_completion_date=form.target_completion_date.data,
            bom_lines=bom_lines,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("work_order.detail", wo_id=wo_id))

    return render_template(
        "work_order/form.html",
        form=form,
        materials=materials,
        warnings=warnings,
        title="Edit Work Order",
        bom_lines=existing_bom,
        wo=wo,
    )


# ------------------------------------------------------------------ #
# Delete (Planner, own PENDING orders only)                          #
# ------------------------------------------------------------------ #

@work_order_bp.route("/<int:wo_id>/delete", methods=["POST"])
@login_required
@requires_role("PLANNER")
def delete(wo_id):
    success, message = delete_work_order(wo_id, current_user.id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("work_order.list"))