"""
decorators/rbac.py

Role-Based Access Control decorator.

Usage:
    @requires_role("MANAGER")
    def my_view(): ...

    @requires_role("PLANNER", "MANAGER")   # allow multiple roles
    def my_view(): ...
"""

from functools import wraps

from flask import abort, flash, redirect, url_for
from flask_login import current_user


def requires_role(*roles):
    """
    Restrict a view to users whose role matches one of the given role strings.
    Returns 403 if the user's role is not in the allowed list.
    """
    def decorator(f):
        @wraps(f)
        def wrapped(*args, **kwargs):
            if not current_user.is_authenticated:
                return redirect(url_for("auth.login"))
            if current_user.role.value not in roles:
                flash("You do not have permission to access that page.", "danger")
                abort(403)
            return f(*args, **kwargs)
        return wrapped
    return decorator
