#!/usr/bin/env python3
import sys, os
from pathlib import Path
sys.path.insert(0, os.path.dirname(__file__))

from app import create_app
from app.extensions import db
from app.models import User
from app.services.venue_seed import seed_venues
from app.services.cricsheet_importer import import_cricsheet_venues


DEMO_EMAIL = os.getenv("DEMO_EMAIL", "demo@cricketlens.example")
DEMO_PASSWORD = os.getenv("DEMO_PASSWORD", "CricketLensDemo123!")
LEGACY_DEMO_EMAIL = "demo@cricketlens.local"


def seed_demo_user():
    user = User.query.filter_by(email=DEMO_EMAIL).first()
    if not user and DEMO_EMAIL != LEGACY_DEMO_EMAIL:
        user = User.query.filter_by(email=LEGACY_DEMO_EMAIL).first()
        if user:
            user.email = DEMO_EMAIL
    if not user:
        user = User(email=DEMO_EMAIL, username="demo")
        db.session.add(user)
    user.set_password(DEMO_PASSWORD)
    db.session.commit()


def seed():
    app = create_app()
    with app.app_context():
        db.create_all()
        venue_count = seed_venues()
        imported_count = import_cricsheet_venues(Path(__file__).parent / "venuedata")
        seed_demo_user()
        print(f"Seeded {venue_count} venues.")
        print(f"Imported Cricsheet data for {imported_count} venues.")
        print(f"Demo login: {DEMO_EMAIL} / {DEMO_PASSWORD}")


if __name__ == "__main__":
    seed()
