"""Seed default database data after migrations have completed."""
from app import create_app
from app.models import seed_boost_plans, seed_default_tasks


app = create_app()

with app.app_context():
    seed_boost_plans()
    seed_default_tasks()