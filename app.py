"""
ManufacturingHub — Flask application factory.

Usage:
    flask --app run db upgrade    # run migrations
    flask --app run run           # start dev server
"""

import os
from datetime import timedelta, timezone

from flask import Flask, redirect, url_for
from flask_login import LoginManager, current_user
from flask_mail import Mail
from flask_migrate import Migrate
from flask_wtf.csrf import CSRFProtect

from models.base import db


csrf         = CSRFProtect()
login_manager = LoginManager()
migrate      = Migrate()
mail         = Mail()
IST_TZ       = timezone(timedelta(hours=5, minutes=30))


def create_app(config_object=None):
    app = Flask(__name__)

    @app.template_filter("format_ist")
    def format_ist(dt, fmt="%d %b %Y, %H:%M:%S"):
        """Render UTC datetime values in IST for templates."""
        if dt is None:
            return "—"
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(IST_TZ).strftime(fmt)

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
    from blueprints.maintenance import maintenance_bp
    from blueprints.notification import notification_bp
    from blueprints.audit import audit_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(profile_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(machine_bp)
    app.register_blueprint(material_bp)
    app.register_blueprint(work_order_bp)
    app.register_blueprint(scheduling_bp)
    app.register_blueprint(maintenance_bp)
    app.register_blueprint(notification_bp)
    app.register_blueprint(audit_bp)

    @app.route("/")
    def root():
        if current_user.is_authenticated:
            return redirect(url_for("dashboard.index"))
        return redirect(url_for("auth.login"))

    # ---- US-8: CLI commands for cron jobs --------------------------------
    # _register_cli_commands(app)

    # ---- US-8 (alternate): In-process APScheduler -------------------------
    # Starts background jobs automatically when the app runs via
    # `python run.py`. No Windows Task Scheduler or crontab needed.

    _start_apscheduler(app)

    return app


# ------------------------------------------------------------------ #
# APScheduler — in-process background job scheduler                    #
# ------------------------------------------------------------------ #

def _start_apscheduler(app):
    """
    Start APScheduler within the Flask app process.

    This is an alternate approach to the CLI + crontab/Windows Task Scheduler
    method. It runs the same notification and maintenance jobs automatically
    in the background while the Flask dev server is running.

    Schedule (configurable via app.config):
      - Low-stock check:          every 6 hours   (US-6 / US-8)
      - Maintenance-due check:    every 6 hours   (US-7 / US-8)
      - Machine status update:    every 6 hours   (US-7)
      - Process notification queue: every 15 minutes (US-8)
    """
    # In debug mode, Flask spawns TWO processes: a parent (reloader) and
    # a child (the actual app). Without this guard, APScheduler would start
    # in BOTH, causing every job to run twice.
    # Fix: only start the scheduler in the child process (WERKZEUG_RUN_MAIN=true).
    if app.debug and os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        return

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
        from apscheduler.triggers.interval import IntervalTrigger
    except ImportError:
        app.logger.warning(
            "APScheduler not installed. Background jobs disabled. "
            "Install with: pip install APScheduler"
        )
        return

    scheduler = BackgroundScheduler(daemon=True)

    # Wrap each job so it runs inside the Flask app context
    def _job_low_stock():
        with app.app_context():
            from services.notification_service import run_low_stock_check
            count = run_low_stock_check()
            if count:
                app.logger.info(f"[APScheduler] Low-stock check: {count} notification(s) enqueued.")

    def _job_maintenance_due():
        with app.app_context():
            from services.notification_service import run_maintenance_due_check
            count = run_maintenance_due_check()
            if count:
                app.logger.info(f"[APScheduler] Maintenance-due check: {count} notification(s) enqueued.")

    def _job_update_machine_status():
        with app.app_context():
            from services.maintenance_service import update_machines_due_for_maintenance
            count = update_machines_due_for_maintenance()
            if count:
                app.logger.info(f"[APScheduler] Machine status update: {count} machine(s) set to MAINTENANCE.")

    def _job_process_queue():
        with app.app_context():
            from services.notification_service import process_notification_queue
            stats = process_notification_queue(batch_size=50)
            sent = stats.get("sent", 0)
            if sent:
                app.logger.info(
                    f"[APScheduler] Queue processed: {sent} sent, "
                    f"{stats['failed']} failed, {stats['skipped']} skipped."
                )

    # Read intervals from config (with sensible defaults)
    check_hours = app.config.get("SCHEDULER_CHECK_HOURS", 1)#for testing use 1 minute instead of 6 hours
    queue_minutes = app.config.get("SCHEDULER_QUEUE_MINUTES", 1)

    scheduler.add_job(
        _job_low_stock,
        trigger=IntervalTrigger(minutes=check_hours),
        id="low_stock_check",
        name="US-6/US-8: Low stock alert scan",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_maintenance_due,
        trigger=IntervalTrigger(minutes=check_hours),
        id="maintenance_due_check",
        name="US-7/US-8: Maintenance due alert scan",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_update_machine_status,
        trigger=IntervalTrigger(minutes=check_hours),
        id="update_machine_status",
        name="US-7: Auto-set machines to MAINTENANCE",
        replace_existing=True,
    )
    scheduler.add_job(
        _job_process_queue,
        trigger=IntervalTrigger(minutes=queue_minutes),
        id="process_notification_queue",
        name="US-8: Send queued notifications",
        replace_existing=True,
    )

    scheduler.start()
    app.logger.info(
        f"[APScheduler] Started — checks every {check_hours}h, "
        f"queue processing every {queue_minutes}min."
    )

    app.logger.info("***************[APScheduler] Scheduler ended************")

    # Shut down gracefully when the app stops
    import atexit
    atexit.register(lambda: scheduler.shutdown(wait=False))


def _register_cli_commands(app):
    """Register Flask CLI commands for notification cron jobs."""
    import click

    @app.cli.group()
    def notify():
        """US-8: Notification & alert commands."""

    @notify.command("low-stock")
    def check_low_stock():
        """Scan materials and enqueue LOW_STOCK alerts to managers."""
        from services.notification_service import run_low_stock_check
        count = run_low_stock_check()
        click.echo(f"Low-stock check complete: {count} notification(s) enqueued.")

    @notify.command("maintenance-due")
    def check_maintenance():
        """Scan rules and enqueue MAINTENANCE_DUE alerts to managers."""
        from services.notification_service import run_maintenance_due_check
        count = run_maintenance_due_check()
        click.echo(f"Maintenance-due check complete: {count} notification(s) enqueued.")

    @notify.command("update-machine-status")
    def update_machine_status():
        """US-7: Auto-set machines to MAINTENANCE when due (±2 days grace)."""
        from services.maintenance_service import update_machines_due_for_maintenance
        count = update_machines_due_for_maintenance()
        click.echo(f"Machine status update complete: {count} machine(s) set to MAINTENANCE.")

    @notify.command("process-queue")
    @click.option("--batch", default=50, help="Max notifications to process per run.")
    def process_queue(batch):
        """Process QUEUED notifications (send emails, retry failures)."""
        from services.notification_service import process_notification_queue
        stats = process_notification_queue(batch_size=batch)
        click.echo(
            f"Queue processed: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped."
        )

    @notify.command("run-all")
    def run_all():
        """Run all daily checks + machine status update + process queue."""
        from services.notification_service import (
            process_notification_queue, run_low_stock_check, run_maintenance_due_check,
        )
        from services.maintenance_service import update_machines_due_for_maintenance

        ls = run_low_stock_check()
        md = run_maintenance_due_check()
        ms = update_machines_due_for_maintenance()
        click.echo(
            f"Enqueued: {ls} low-stock + {md} maintenance-due notifications. "
            f"{ms} machine(s) set to MAINTENANCE."
        )
        stats = process_notification_queue()
        click.echo(
            f"Queue processed: {stats['sent']} sent, "
            f"{stats['failed']} failed, {stats['skipped']} skipped."
        )
