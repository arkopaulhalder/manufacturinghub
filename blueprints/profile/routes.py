"""
blueprints/profile/routes.py

US-2 routes: view profile, edit profile.
After profile save, redirects to role-based dashboard per SRS.
"""

from flask import flash, redirect, render_template, request, url_for
from flask_login import current_user, login_required

from services.profile_service import (
    dashboard_url_for_role,
    get_profile,
    update_profile,
)

from . import profile_bp
from .forms import ProfileForm


# ------------------------------------------------------------------ #
# View profile — US-2                                                 #
# ------------------------------------------------------------------ #

@profile_bp.route("/")
@login_required
def view():
    success, message, user = get_profile(
        user_id=current_user.id,
        requesting_user_id=current_user.id,
    )
    if not success:
        flash(message, "danger")
        return redirect(url_for("dashboard.index"))

    return render_template("profile/view.html", user=user)


# ------------------------------------------------------------------ #
# Edit profile — US-2                                                 #
# ------------------------------------------------------------------ #

@profile_bp.route("/edit", methods=["GET", "POST"])
@login_required
def edit():
    form = ProfileForm()

    # Pre-fill form with existing data on GET — SRS Dos
    if request.method == "GET":
        form.full_name.data             = current_user.full_name
        form.department.data            = current_user.department
        form.phone.data                 = current_user.phone
        form.notification_preference.data = (
            current_user.notification_preference.value
            if current_user.notification_preference else "NONE"
        )

    if form.validate_on_submit():
        success, message = update_profile(
            user_id=current_user.id,
            requesting_user_id=current_user.id,
            full_name=form.full_name.data,
            department=form.department.data,
            phone=form.phone.data,
            notification_preference=form.notification_preference.data,
            ip_address=request.remote_addr,
        )
        if success:
            flash(message, "success")
            # SRS: profile completion triggers role-based dashboard redirection
            return redirect(url_for(dashboard_url_for_role(current_user)))
        flash(message, "danger")

    return render_template("profile/edit.html", form=form)