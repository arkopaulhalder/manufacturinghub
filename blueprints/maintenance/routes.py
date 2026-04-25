"""
blueprints/maintenance/routes.py — US-7 Preventive Maintenance Scheduling.

SRS RBAC:
  - Create / Edit / Delete rules: MANAGER only
  - Log maintenance: MANAGER only
  - View rules and logs: MANAGER (+ potentially PLANNER read-only)

Routes:
  GET  /maintenance/                     — List all rules
  GET  /maintenance/new                  — Create rule form
  POST /maintenance/new                  — Submit new rule
  GET  /maintenance/<rule_id>/edit       — Edit rule form
  POST /maintenance/<rule_id>/edit       — Submit rule update
  POST /maintenance/<rule_id>/delete     — Delete rule
  GET  /maintenance/<rule_id>/log        — Log maintenance form
  POST /maintenance/<rule_id>/log        — Submit maintenance log
  GET  /maintenance/<rule_id>/history    — View logs for a rule
"""

from datetime import datetime, timedelta, timezone

from flask import flash, redirect, render_template, request, url_for
from flask_login import login_required, current_user

from decorators.rbac import requires_role
from models.machine import Machine
from services.maintenance_service import (
    create_rule,
    delete_rule,
    get_all_rules,
    get_logs_for_rule,
    get_rule_by_id,
    log_maintenance,
    update_rule,
)
from . import maintenance_bp
from .forms import MaintenanceLogForm, MaintenanceRuleForm


# ------------------------------------------------------------------ #
# List all maintenance rules                                          #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/")
@login_required
@requires_role("MANAGER")
def list():
    rules = get_all_rules()
    now_utc = datetime.now(timezone.utc)
    soon_utc = now_utc + timedelta(days=7)
    return render_template(
        "maintenance/list.html",
        rules=rules,
        now_utc=now_utc,
        soon_utc=soon_utc,
    )


# ------------------------------------------------------------------ #
# Create rule (Manager only)                                          #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/new", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def create():
    form = MaintenanceRuleForm()

    machines = Machine.query.order_by(Machine.machine_id).all()
    form.machine_id.choices = [
        (m.id, f"{m.machine_id} — {m.name}")
        for m in machines
    ]

    if not machines:
        flash("No machines available. Add machines first.", "warning")
        return redirect(url_for("maintenance.list"))

    if form.validate_on_submit():
        last_date = form.last_maintenance_date.data
        if last_date:
            last_date = last_date.replace(tzinfo=timezone.utc)

        success, message, rule = create_rule(
            machine_pk=form.machine_id.data,
            frequency_str=form.frequency.data,
            interval_value=form.interval_value.data,
            last_maintenance_date=last_date,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("maintenance.list"))

    return render_template(
        "maintenance/form.html",
        form=form,
        title="Create Maintenance Rule",
    )


# ------------------------------------------------------------------ #
# Edit rule (Manager only)                                            #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/<int:rule_id>/edit", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def edit(rule_id):
    rule = get_rule_by_id(rule_id)
    if not rule:
        flash("Maintenance rule not found.", "danger")
        return redirect(url_for("maintenance.list"))

    form = MaintenanceRuleForm(obj=rule)

    machines = Machine.query.order_by(Machine.machine_id).all()
    form.machine_id.choices = [
        (m.id, f"{m.machine_id} — {m.name}")
        for m in machines
    ]

    if request.method == "GET":
        form.machine_id.data = rule.machine_id
        form.frequency.data = rule.frequency.value
        form.interval_value.data = rule.interval_value
        if rule.last_maintenance_date:
            form.last_maintenance_date.data = rule.last_maintenance_date.replace(tzinfo=None)

    if form.validate_on_submit():
        last_date = form.last_maintenance_date.data
        if last_date:
            last_date = last_date.replace(tzinfo=timezone.utc)

        success, message = update_rule(
            rule_pk=rule_id,
            frequency_str=form.frequency.data,
            interval_value=form.interval_value.data,
            last_maintenance_date=last_date,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("maintenance.list"))

    return render_template(
        "maintenance/form.html",
        form=form,
        title="Edit Maintenance Rule",
        rule=rule,
    )


# ------------------------------------------------------------------ #
# Delete rule (Manager only)                                          #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/<int:rule_id>/delete", methods=["POST"])
@login_required
@requires_role("MANAGER")
def delete(rule_id):
    success, message = delete_rule(rule_id)
    flash(message, "success" if success else "danger")
    return redirect(url_for("maintenance.list"))


# ------------------------------------------------------------------ #
# Log maintenance (Manager only)                                      #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/<int:rule_id>/log", methods=["GET", "POST"])
@login_required
@requires_role("MANAGER")
def log(rule_id):
    rule = get_rule_by_id(rule_id)
    if not rule:
        flash("Maintenance rule not found.", "danger")
        return redirect(url_for("maintenance.list"))

    form = MaintenanceLogForm()

    if request.method == "GET":
        form.date.data = datetime.now()

    if form.validate_on_submit():
        log_date = form.date.data
        if log_date:
            log_date = log_date.replace(tzinfo=timezone.utc)

        success, message, log_entry = log_maintenance(
            rule_pk=rule_id,
            date=log_date,
            performed_by=form.performed_by.data,
            notes=form.notes.data,
            user_id=current_user.id,
            ip_address=request.remote_addr,
        )
        flash(message, "success" if success else "danger")
        if success:
            return redirect(url_for("maintenance.list"))

    return render_template(
        "maintenance/log_form.html",
        form=form,
        rule=rule,
    )


# ------------------------------------------------------------------ #
# View maintenance history for a rule                                 #
# ------------------------------------------------------------------ #

@maintenance_bp.route("/<int:rule_id>/history")
@login_required
@requires_role("MANAGER")
def history(rule_id):
    rule = get_rule_by_id(rule_id)
    if not rule:
        flash("Maintenance rule not found.", "danger")
        return redirect(url_for("maintenance.list"))

    logs = get_logs_for_rule(rule_id)
    return render_template(
        "maintenance/history.html",
        rule=rule,
        logs=logs,
    )
