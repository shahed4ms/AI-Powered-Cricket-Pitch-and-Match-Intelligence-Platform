from flask import Blueprint

analysis_bp = Blueprint("analysis", __name__, url_prefix="/analysis")

from app.analysis import routes  # noqa: E402, F401
