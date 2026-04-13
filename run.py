"""
run.py — development entry point.

Usage:
    python run.py
    flask --app run db upgrade
    flask --app run db migrate -m "description"
"""

from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=app.config.get("DEBUG", False))