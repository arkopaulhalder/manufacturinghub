from flask import render_template, redirect, url_for
from flask_login import login_required, current_user
from models import UserRole

from . import dashboard_bp

@dashboard_bp.route("/")
@login_required
def index():
    if current_user.role == UserRole.MANAGER:
        return redirect(url_for("dashboard.manager"))
    return redirect(url_for("dashboard.planner"))

@dashboard_bp.route('/manager')
@login_required
def manager():
    return render_template('dashboard/manager.html', title='Manager Dashboard')

@dashboard_bp.route("/planner")
@login_required
def planner():
    return render_template("dashboard/planner.html")