"""
ManufacturingHub — Flask application factory.

Usage:
    flask --app manufacturinghub.app db upgrade   # run Alembic migrations
    flask --app manufacturinghub.app run          # start dev server
"""

import os

from flask import Flask
from flask_login import LoginManager
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from models.base import db


csrf = CSRFProtect()
login_manager = LoginManager()
migrate = Migrate()


def create_app(config_object=None):
    app = Flask(__name__)

    # ---- Configuration --------------------------------------------------
    app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY", "change-me-in-production")
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/manufacturinghub",
    )
    app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
    app.config["SQLALCHEMY_ENGINE_OPTIONS"] = {
        "pool_pre_ping": True,          # recycle stale connections
        "pool_recycle": 280,
    }

    if config_object:
        app.config.from_object(config_object)

    # ---- Extensions -----------------------------------------------------
    db.init_app(app)
    csrf.init_app(app)
    login_manager.init_app(app)
    migrate.init_app(app, db, directory="manufacturinghub/migrations")

    login_manager.login_view = "auth.login"
    login_manager.login_message_category = "warning"

    @login_manager.user_loader
    def load_user(user_id):
        from models.user import User
        return User.query.get(int(user_id))

    # ---- Blueprints (register as you build each module) -----------------
    from blueprints.auth import auth_bp
    app.register_blueprint(auth_bp)

    # ---- Root redirect --------------------------------------------------
    from flask import redirect, url_for

    @app.route("/")
    def index():
        return redirect(url_for("auth.login"))

    return app