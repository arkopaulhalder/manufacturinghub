"""
Create all tables in MySQL (development bootstrap).

Usage:
    python create_tables.py

For production, prefer Flask-Migrate (`flask db migrate` / `flask db upgrade`) so
schema changes (e.g. CHECK constraints) are versioned. If tables already exist,
`create_all()` will not alter them; apply migrations or recreate tables to pick up
new constraints.
"""

from app import create_app
from models.base import db

# Import ALL models so SQLAlchemy knows about them before create_all()
import models.user
import models.audit
import models.notification
import models.inventory
import models.machine
import models.maintenance
import models.work_order
import models.material

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ All tables created successfully in 'manufacturinghub' database!")
