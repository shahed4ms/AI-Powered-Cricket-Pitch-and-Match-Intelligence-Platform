import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    SECRET_KEY = os.getenv("FLASK_SECRET_KEY", "dev-secret-key-change-in-production")
    SQLALCHEMY_DATABASE_URI = os.getenv("FLASK_DATABASE_URL", "sqlite:///cricketlens.db")
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    GOOGLE_OAUTH_CLIENT_ID = os.getenv("GOOGLE_OAUTH_CLIENT_ID")
    GOOGLE_OAUTH_CLIENT_SECRET = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET")

    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
    GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
    GEMINI_BASE_URL = os.getenv(
        "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
    )
    GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-3.6-flash")
    CRICKETDATA_API_KEY = os.getenv("CRICKETDATA_API_KEY")

    MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB max upload
    UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), "static", "uploads")


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    DEBUG = False


config = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig,
}


def validate_configuration(app):
    """Log safe startup diagnostics for local and optional integrations."""
    warnings = []

    if not app.config.get("SECRET_KEY") or app.config.get("SECRET_KEY") == "dev-secret-key-change-in-production":
        warnings.append("FLASK_SECRET_KEY is using a development fallback")

    optional_providers = {
        "GOOGLE_OAUTH_CLIENT_ID": "Google sign-in",
        "GOOGLE_OAUTH_CLIENT_SECRET": "Google sign-in",
        "CRICKETDATA_API_KEY": "CricketData venue search",
    }
    if not app.config.get("OPENAI_API_KEY") and not app.config.get("GEMINI_API_KEY"):
        warnings.append("OPENAI_API_KEY or GEMINI_API_KEY is not configured; AI features will use their fallback")
    for key, provider in optional_providers.items():
        if not str(app.config.get(key) or "").strip():
            warnings.append(f"{key} is not configured; {provider} will use its fallback")

    app.config["CRICKETLENS_CONFIG_WARNINGS"] = warnings
    for warning in warnings:
        app.logger.warning("Configuration: %s", warning)

    return warnings
