"""
blueprints/material/routes.py — US-3 Material CRUD.

SRS RBAC:
  - List/view: PLANNER + MANAGER
  - Create/Edit/Delete: MANAGER only
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required

from decorators.rbac import requires_role
from services.material_service import (
    create_material, delete_material, get_all_materials,
    get_material_by_id, update_material,
)
from . import material_bp
from .forms import MaterialForm


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
    success, message = delete_material(material_pk)
    flash(message, "success" if success else "danger")
    return redirect(url_for("material.list"))