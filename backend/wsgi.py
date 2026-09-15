"""Flask-Migrate / Alembic configuration."""
from flask.cli import FlaskGroup
from app import create_app
from app.database import db

app = create_app()
