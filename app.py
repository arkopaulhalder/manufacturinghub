"""
ManufacturingHub — Flask application factory.

Usage:
    flask --app run db upgrade    # run migrations
    flask --app run run           # start dev server
"""

import os

from flask import Flask
from flask_login import LoginManager
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from models.base import db


csrf         = CSRFProtect()
login_manager = LoginManager()
migrate      = Migrate()
mail         = Mail()


def create_app(config_object=None):
    app = Flask(__name__)

    # ---- Configuration --------------------------------------------------
    from config import config_map
    env = os.environ.get("FLASK_ENV", "development")
    app.config.from_object(config_map.get(env, config_map["development"]))

    if config_object:
        app.config.from_object(config_object)

    # ---- Extensions -----------------------------------------------------
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, directory="migrations")
    mail.init_app(app)

    from models import (
        User,
        Machine,
        Material,
        WorkOrder,
        WorkOrderMaterial,
        InventoryMovement,
        MaintenanceRule,
        MaintenanceLog,
        Notification,
        AuditLog
    )

    login_manager.login_view         = "auth.login"
    login_manager.login_message      = "Please log in to access this page."
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    # ---- Blueprints -----------------------------------------------------
    from blueprints.auth        import auth_bp
    from blueprints.profile     import profile_bp
    from blueprints.dashboard   import dashboard_bp
    from blueprints.machine     import machine_bp
    from blueprints.material    import material_bp
    from blueprints.work_order  import work_order_bp
    from blueprints.scheduling  import scheduling_bp
 
    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(machine_bp)
    app.register_blueprint(material_bp)
    app.register_blueprint(work_order_bp)
    app.register_blueprint(scheduling_bp)

    return app