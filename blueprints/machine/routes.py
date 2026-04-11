"""
blueprints/machine/routes.py — US-3 Machine CRUD.

SRS RBAC:
  - List/view: PLANNER + MANAGER (read-only for planner)
  - Create/Edit/Delete: MANAGER only
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from decorators.rbac import requires_role
from services.machine_service import (
    create_machine, delete_machine, get_all_machines,
    get_machine_by_id, update_machine,
)
from . import machine_bp
from .forms import MachineForm


# ---- List (Planner + Manager) ------------------------------------

@machine_bp.route("/")
@login_required
def list():
    machines = get_all_machines()
    return render_template("machine/list.html", machines=machines)


# ---- Create (Manager only) ---------------------------------------

@machine_bp.route("/new", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def create():
    form = MachineForm()
    if form.validate_on_submit():
        success, message = create_machine(
            machine_id=form.machine_id.data,
            name=form.name.data,
            type_str=form.type.data,
            capacity_per_hour=form.capacity_per_hour.data,
            status_str=form.status.data,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("machine.list"))
    return render_template("machine/form.html", form=form, title="Add Machine")


# ---- Edit (Manager only) -----------------------------------------

@machine_bp.route("/<int:machine_pk>/edit", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def edit(machine_pk):
    machine = get_machine_by_id(machine_pk)
    if not machine:
        flash("Machine not found.", "danger")
        return redirect(url_for("machine.list"))

    form = MachineForm(obj=machine)

    if request.method == "GET":
        form.type.data   = machine.type.value
        form.status.data = machine.status.value

    if form.validate_on_submit():
        success, message = update_machine(
            machine_pk=machine_pk,
            machine_id=form.machine_id.data,
            name=form.name.data,
            type_str=form.type.data,
            capacity_per_hour=form.capacity_per_hour.data,
            status_str=form.status.data,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("machine.list"))

    return render_template("machine/form.html", form=form, title="Edit Machine", machine=machine)


# ---- Delete (Manager only) ---------------------------------------

@machine_bp.route("/<int:machine_pk>/delete", methods=["POST"])
@login_required
@requires_role("MANAGER")
def delete(machine_pk):
    success, message = delete_machine(machine_pk)
    flash(message, "success" if success else "danger")
    return redirect(url_for("machine.list"))