"""
Run this ONCE to create all tables in MySQL.
Usage:
    .\.projectenv\Scripts\python.exe create_tables.py
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

app = create_app()

with app.app_context():
    db.create_all()
    print("✅ All tables created successfully in 'manufacturinghub' database!")
