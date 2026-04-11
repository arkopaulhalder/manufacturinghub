"""
config.py — reads environment variables (from .env via python-dotenv).
Import the right class in create_app() based on FLASK_ENV.
"""

import os
from dotenv import load_dotenv

load_dotenv()  # loads .env file into os.environ


class BaseConfig:
    SECRET_KEY = os.environ.get("SECRET_KEY", "change-me")
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Flask-Mail
    # Port 587 → MAIL_USE_TLS=true,  MAIL_USE_SSL=false  (Gmail default)
    # Port 465 → MAIL_USE_TLS=false, MAIL_USE_SSL=true
    MAIL_SERVER          = os.environ.get("MAIL_SERVER", "smtp.gmail.com")
    MAIL_PORT            = int(os.environ.get("MAIL_PORT", 587))
    MAIL_USE_TLS         = os.environ.get("MAIL_USE_TLS", "true").lower() == "true"
    MAIL_USE_SSL         = os.environ.get("MAIL_USE_SSL", "false").lower() == "true"
    MAIL_USERNAME        = os.environ.get("MAIL_USERNAME")
    MAIL_PASSWORD        = os.environ.get("MAIL_PASSWORD")
    MAIL_DEFAULT_SENDER  = os.environ.get("MAIL_DEFAULT_SENDER", "noreply@manufacturinghub.com")

    # Used by url_for(_external=True) to build the reset link correctly.
    # In dev this is set per-request. In production set SERVER_NAME in .env
    # e.g. SERVER_NAME=manufacturinghub.com
    SERVER_NAME          = os.environ.get("SERVER_NAME")

    # Rate-limit (US-1)
    LOGIN_MAX_ATTEMPTS  = 5
    LOGIN_LOCKOUT_MINS  = 15

    # Password reset token expiry in seconds (US-1: 1 hour)
    RESET_TOKEN_EXPIRY  = 3600


class DevelopmentConfig(BaseConfig):
    DEBUG = True
    # In dev, url_for(_external=True) uses the dev server host automatically.
    # Do NOT set SERVER_NAME in dev — it breaks the request context.
    SERVER_NAME = None
    SQLALCHEMY_DATABASE_URI = os.environ.get(
        "DATABASE_URL",
        "mysql+pymysql://root:password@localhost:3306/manufacturinghub"
    )


class ProductionConfig(BaseConfig):
    DEBUG = False
    SQLALCHEMY_DATABASE_URI = os.environ.get("DATABASE_URL")


class TestingConfig(BaseConfig):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"
    WTF_CSRF_ENABLED = False
    # Needed so url_for(_external=True) works in tests without a real request
    SERVER_NAME = "localhost"


config_map = {
    "development": DevelopmentConfig,
    "production":  ProductionConfig,
    "testing":     TestingConfig,
}