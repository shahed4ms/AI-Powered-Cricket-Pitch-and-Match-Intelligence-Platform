import os
from sqlalchemy import inspect, text
from flask import Flask
from flask_dance.contrib.google import make_google_blueprint
from app.config import config, validate_configuration
from app.extensions import db, migrate, login_manager, csrf, limiter


def _ensure_demo_user():
    from app.models import User

    demo_email = os.getenv("DEMO_EMAIL", "demo@cricketlens.example")
    demo_password = os.getenv("DEMO_PASSWORD", "CricketLensDemo123!")
    user = User.query.filter(db.func.lower(User.email) == demo_email.lower()).first()
    if user is None:
        legacy = User.query.filter_by(email="demo@cricketlens.local").first()
        if legacy:
            legacy.email = demo_email
            user = legacy
        else:
            user = User(email=demo_email, username="demo")
            db.session.add(user)
    user.username = user.username or "demo"
    user.set_password(demo_password)
    db.session.commit()
    return user


def create_app(config_name=None):
    if config_name is None:
        config_name = os.getenv("FLASK_ENV", "development")

    app = Flask(__name__)
    app.config.from_object(config[config_name])
    validate_configuration(app)

    os.makedirs(app.config.get("UPLOAD_FOLDER", "app/static/uploads"), exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    from pathlib import Path
    from app.models import User, Venue, VenueFormatStats
    from app.services.venue_seed import seed_venues
    from app.services.cricsheet_importer import import_cricsheet_json

    @login_manager.user_loader
    def load_user(user_id):
        return db.session.get(User, int(user_id))

    google_client_id = app.config.get("GOOGLE_OAUTH_CLIENT_ID")
    google_client_secret = app.config.get("GOOGLE_OAUTH_CLIENT_SECRET")
    if google_client_id and google_client_secret:
        google_bp = make_google_blueprint(
            client_id=google_client_id,
            client_secret=google_client_secret,
            scope=["openid", "email", "profile"],
            redirect_to="auth.google_login",
        )
        app.register_blueprint(google_bp)

    from app.auth import auth_bp
    from app.dashboard import dashboard_bp
    from app.analysis import analysis_bp
    from app.profile import profile_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(analysis_bp)
    app.register_blueprint(profile_bp)

    with app.app_context():
        db.create_all()
        _upgrade_local_schema()
        seed_venues()
        if not VenueFormatStats.query.first():
            json_dir = Path(__file__).resolve().parent.parent / "all_json"
            if json_dir.exists():
                import_cricsheet_json(json_dir)
        _ensure_demo_user()

    @app.route("/")
    def index():
        from flask_login import current_user
        if current_user.is_authenticated:
            from flask import redirect, url_for
            return redirect(url_for("dashboard.index"))
        from flask import redirect, url_for
        return redirect(url_for("auth.login"))

    return app


def _upgrade_local_schema():
    """Add new local SQLite columns without changing existing user data."""
    inspector = inspect(db.engine)
    columns = {
        "users": {
            "time_format": "VARCHAR(10) DEFAULT '24h'",
            "temperature_unit": "VARCHAR(2) DEFAULT 'C'",
        },
        "matches": {
            "result_status": "VARCHAR(20) DEFAULT 'pending'",
            "result_outcome": "VARCHAR(20)",
            "toss_outcome": "VARCHAR(10)",
            "batting_innings": "VARCHAR(10)",
            "own_score": "VARCHAR(30)",
            "opponent_score": "VARCHAR(30)",
            "toss_decision": "VARCHAR(20)",
            "batting_first_team": "VARCHAR(255)",
            "innings_first_score": "VARCHAR(30)",
            "innings_second_score": "VARCHAR(30)",
        },
        "reviews": {
            "review_data": "JSON",
        },
    }
    for table, additions in columns.items():
        existing = {column["name"] for column in inspector.get_columns(table)}
        for name, definition in additions.items():
            if name not in existing:
                db.session.execute(text(f"ALTER TABLE {table} ADD COLUMN {name} {definition}"))
    db.session.commit()
