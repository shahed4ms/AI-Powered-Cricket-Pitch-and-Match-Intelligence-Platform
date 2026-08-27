from datetime import timedelta
from flask import current_app, render_template, redirect, url_for, flash, request, jsonify
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
import os, uuid
from app.dashboard import dashboard_bp
from app.dashboard.forms import MatchForm
from app.extensions import db, limiter
from app.models import Venue, Match
from app.services import venue_service


@dashboard_bp.route("/", methods=["GET"])
@login_required
def index():
    form = MatchForm()
    venues = Venue.query.order_by(Venue.name).limit(50).all()
    pending_matches = Match.query.filter(
        Match.user_id == current_user.id,
        db.or_(Match.result_status == "pending", Match.result_status.is_(None)),
    ).order_by(Match.date_start.desc()).all()
    reviewed_matches = Match.query.filter(
        Match.user_id == current_user.id,
        Match.result_status == "completed",
    ).order_by(Match.date_start.desc()).limit(20).all()
    return render_template("dashboard.html", form=form, venues=venues, pending_matches=pending_matches, reviewed_matches=reviewed_matches)


@dashboard_bp.route("/create-match", methods=["POST"])
@login_required
@limiter.limit("10/minute")
def create_match():
    form = MatchForm()
    if not form.validate_on_submit():
        validation_errors = {
            field_name: messages
            for field_name, messages in form.errors.items()
            if field_name not in {"password", "confirm_password"}
        }
        current_app.logger.warning(
            "Match form validation failed for user_id=%s fields=%s",
            current_user.id,
            validation_errors,
        )
        flash("Please fill in all required fields.", "error")
        return redirect(url_for("dashboard.index"))

    if form.format.data == "Test":
        if not form.date_end.data:
            form.date_end.data = form.date_start.data + timedelta(days=5)
        elif form.date_end.data < form.date_start.data or form.date_end.data > form.date_start.data + timedelta(days=5):
            flash("Test matches can cover a maximum five days from the start date.", "error")
            return redirect(url_for("dashboard.index"))

    venue = Venue.query.get(int(form.venue_id.data))
    if not venue:
        flash("Invalid venue selected.", "error")
        return redirect(url_for("dashboard.index"))

    match = Match(
        user_id=current_user.id,
        venue_id=venue.id,
        match_name=form.match_name.data,
        format=form.format.data,
        date_start=form.date_start.data,
        date_end=form.date_end.data if form.format.data == "Test" else None,
        time_start=form.time_start.data,
        time_end=form.time_end.data,
        ball_type=form.ball_type.data if form.ball_type.data else None,
    )

    if form.pitch_image.data:
        file = form.pitch_image.data
        filename = secure_filename(file.filename)
        ext = filename.rsplit(".", 1)[-1].lower()
        unique_name = f"{uuid.uuid4().hex}.{ext}"
        upload_dir = os.path.join(os.path.dirname(__file__), "..", "static", "uploads")
        os.makedirs(upload_dir, exist_ok=True)
        file.save(os.path.join(upload_dir, unique_name))
        match.pitch_image_path = f"uploads/{unique_name}"

    try:
        db.session.add(match)
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Match creation failed for user_id=%s", current_user.id)
        flash("Could not create the match. Please try again.", "error")
        return redirect(url_for("dashboard.index"))

    return redirect(url_for("analysis.index", match_id=match.id))


@dashboard_bp.route("/api/venues", methods=["GET"])
@login_required
def search_venues():
    query = request.args.get("q", "").strip()
    if len(query) < 1:
        return jsonify([])

    venues = venue_service.search_venues(query, current_app.config.get("CRICKETDATA_API_KEY"))
    return jsonify(venues[:10])


@dashboard_bp.route("/api/venues/nearby", methods=["POST"])
@login_required
def nearby_venues():
    data = request.get_json()
    lat = data.get("latitude")
    lon = data.get("longitude")
    if lat is None or lon is None:
        return jsonify({"error": "Coordinates required"}), 400

    venues = Venue.query.filter(
        Venue.latitude.isnot(None),
        Venue.longitude.isnot(None),
    ).all()

    from math import asin, cos, radians, sin, sqrt

    def dist(v):
        venue_lat = radians(float(v.latitude))
        venue_lon = radians(float(v.longitude))
        target_lat = radians(float(lat))
        target_lon = radians(float(lon))
        delta_lat = venue_lat - target_lat
        delta_lon = venue_lon - target_lon
        haversine = sin(delta_lat / 2) ** 2 + cos(target_lat) * cos(venue_lat) * sin(delta_lon / 2) ** 2
        return 6371 * 2 * asin(sqrt(haversine))

    venues.sort(key=dist)
    return jsonify([v.to_dict() for v in venues[:5]])
