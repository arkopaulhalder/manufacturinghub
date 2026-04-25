"""
blueprints/material/routes.py — US-3 Material CRUD.

SRS RBAC:
  - List/view: PLANNER + MANAGER
  - Create/Edit/Delete: MANAGER only
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from decorators.rbac import requires_role
from services.material_service import (
    create_material, delete_material, get_all_materials,
    get_material_by_id, update_material,
)
from services.inventory_service import (
    adjust_material, get_movements_for_material, restock_material,
)
from . import material_bp
from .forms import AdjustForm, MaterialForm, RestockForm


# ---- List (Planner + Manager) ------------------------------------

@material_bp.route("/")
@login_required
def list():
    materials = get_all_materials()
    return render_template("material/list.html", materials=materials)


# ---- Create (Manager only) ---------------------------------------

@material_bp.route("/new", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def create():
    form = MaterialForm()
    if form.validate_on_submit():
        success, message = create_material(
            sku=form.sku.data,
            name=form.name.data,
            unit_str=form.unit.data,
            current_stock=form.current_stock.data,
            reorder_level=form.reorder_level.data,
            unit_cost=form.unit_cost.data,
            user_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("material.list"))
    return render_template("material/form.html", form=form, title="Add Material")


# ---- Edit (Manager only) -----------------------------------------

@material_bp.route("/<int:material_pk>/edit", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def edit(material_pk):
    material = get_material_by_id(material_pk)
    if not material:
        flash("Material not found.", "danger")
        return redirect(url_for("material.list"))

    form = MaterialForm(obj=material)

    if request.method == "GET":
        form.unit.data = material.unit.value

    if form.validate_on_submit():
        success, message = update_material(
            material_pk=material_pk,
            sku=form.sku.data,
            name=form.name.data,
            unit_str=form.unit.data,
            current_stock=form.current_stock.data,
            reorder_level=form.reorder_level.data,
            unit_cost=form.unit_cost.data,
            user_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("material.list"))

    return render_template("material/form.html", form=form, title="Edit Material", material=material)


# ---- Delete (Manager only) ---------------------------------------

@material_bp.route("/<int:material_pk>/delete", methods=["POST"])
@login_required
@requires_role("MANAGER")
def delete(material_pk):
    success, message = delete_material(material_pk, user_id=current_user.id, ip_address=request.remote_addr)
    flash(message, "success" if success else "danger")
    return redirect(url_for("material.list"))


# ------------------------------------------------------------------ #
# US-6 — Restock (Manager only)                                       #
# ------------------------------------------------------------------ #

@material_bp.route("/<int:material_pk>/restock", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def restock(material_pk):
    """Add stock to a material via IN movement."""
    material = get_material_by_id(material_pk)
    if not material:
        flash("Material not found.", "danger")
        return redirect(url_for("material.list"))

    form = RestockForm()

    if form.validate_on_submit():
        success, message, alert = restock_material(
            material_pk=material_pk,
            qty=float(form.qty.data),
            supplier=form.supplier.data,
            user_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash(message, "success" if success else "danger")
        if alert:
            flash(
                f"Low stock alert: {alert['sku']} — "
                f"Stock: {alert['current_stock']} {alert['unit']}, "
                f"Reorder level: {alert['reorder_level']} {alert['unit']}",
                "warning"
            )
        if success:
            return redirect(url_for("material.list"))

    return render_template(
        "material/restock.html",
        form=form,
        material=material,
    )


# ------------------------------------------------------------------ #
# US-6 — Adjust (Manager only)                                        #
# ------------------------------------------------------------------ #

@material_bp.route("/<int:material_pk>/adjust", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def adjust(material_pk):
    """Adjust stock via ADJUST movement (can be + or -)."""
    material = get_material_by_id(material_pk)
    if not material:
        flash("Material not found.", "danger")
        return redirect(url_for("material.list"))

    form = AdjustForm()

    if form.validate_on_submit():
        success, message, alert = adjust_material(
            material_pk=material_pk,
            qty_delta=float(form.qty_delta.data),
            reason=form.reason.data,
            user_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash(message, "success" if success else "danger")
        if alert:
            flash(
                f"Low stock alert: {alert['sku']} — "
                f"Stock: {alert['current_stock']} {alert['unit']}, "
                f"Reorder level: {alert['reorder_level']} {alert['unit']}",
                "warning"
            )
        if success:
            return redirect(url_for("material.list"))

    return render_template(
        "material/adjust.html",
        form=form,
        material=material,
    )


# ------------------------------------------------------------------ #
# US-6 — Movement history (Manager + Planner read-only)               #
# ------------------------------------------------------------------ #

@material_bp.route("/<int:material_pk>/movements")
@login_required
def movements(material_pk):
    """View inventory movement history for a material."""
    material = get_material_by_id(material_pk)
    if not material:
        flash("Material not found.", "danger")
        return redirect(url_for("material.list"))

    history = get_movements_for_material(material_pk)
    return render_template(
        "material/movements.html",
        material=material,
        movements=history,
    )