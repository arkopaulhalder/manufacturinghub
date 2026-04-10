from flask import render_template, flash, redirect, url_for, request
from flask_login import login_required, current_user
from . import profile_bp
from .forms import ProfileForm
from models.base import db

@profile_bp.route('/edit', methods=['GET', 'POST'])
@login_required
def edit():
    form = ProfileForm()
    if form.validate_on_submit():
        current_user.full_name = form.full_name.data
        current_user.department = form.department.data
        current_user.phone = form.phone.data
        current_user.notification_preference = form.notification_preference.data
        db.session.commit()
        flash('Your changes have been saved.')
        
        # Role-based redirection
        if current_user.role == 'MANAGER':
            return redirect(url_for('dashboard.manager')) # Placeholder
        else:
            return redirect(url_for('dashboard.index')) # Placeholder
            
    elif request.method == 'GET':
        form.full_name.data = current_user.full_name
        form.department.data = current_user.department
        form.phone.data = current_user.phone
        form.notification_preference.data = current_user.notification_preference
    return render_template('profile/edit.html', title='Edit Profile', form=form)
