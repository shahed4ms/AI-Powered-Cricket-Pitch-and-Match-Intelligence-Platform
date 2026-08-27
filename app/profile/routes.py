import os
import uuid
from flask import current_app, render_template, redirect, url_for, flash, jsonify, request
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename
from app.profile import profile_bp
from app.extensions import db, limiter
from app.models import User, Match, Analysis, Review


@profile_bp.route("/", methods=["GET"])
@login_required
def index():
    matches = Match.query.filter_by(user_id=current_user.id).order_by(Match.created_at.desc()).all()
    analyses = []
    for m in matches:
        a = Analysis.query.filter_by(match_id=m.id).first()
        r = Review.query.filter_by(analysis_id=a.id).first() if a else None
        analyses.append({"match": m, "analysis": a, "review": r})
    stats = {}
    for format_name in ("Test", "ODI", "T20", "Custom"):
        completed = [m for m in matches if m.format == format_name and m.result_status == "completed"]
        stats[format_name] = {
            "played": len(completed),
            "won": sum(m.result_outcome == "won" for m in completed),
            "lost": sum(m.result_outcome == "lost" for m in completed),
        }
    return render_template("profile.html", user=current_user, analyses=analyses, stats=stats)


@profile_bp.route("/settings", methods=["POST"])
@login_required
def settings():
    time_format = request.form.get("time_format")
    temperature_unit = request.form.get("temperature_unit")
    if time_format in {"12h", "24h"}:
        current_user.time_format = time_format
    if temperature_unit in {"C", "F"}:
        current_user.temperature_unit = temperature_unit
    db.session.commit()
    flash("Settings saved.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/avatar", methods=["POST"])
@login_required
def upload_avatar():
    image = request.files.get("avatar")
    if not image or not image.filename:
        flash("Choose a profile picture first.", "error")
        return redirect(url_for("profile.index"))

    extension = secure_filename(image.filename).rsplit(".", 1)[-1].lower()
    if extension not in {"jpg", "jpeg", "png", "webp"}:
        flash("Profile pictures must be JPG, PNG, or WebP files.", "error")
        return redirect(url_for("profile.index"))

    filename = f"avatar_{uuid.uuid4().hex}.{extension}"
    upload_dir = os.path.join(current_app.config["UPLOAD_FOLDER"])
    os.makedirs(upload_dir, exist_ok=True)
    image.save(os.path.join(upload_dir, filename))
    current_user.avatar_url = url_for("static", filename=f"uploads/{filename}")
    db.session.commit()
    flash("Profile picture updated.", "success")
    return redirect(url_for("profile.index"))


@profile_bp.route("/review/<int:analysis_id>", methods=["POST"])
@login_required
@limiter.limit("20/minute")
def submit_review(analysis_id):
    analysis = Analysis.query.get_or_404(analysis_id)
    existing = Review.query.filter_by(analysis_id=analysis_id, user_id=current_user.id).first()
    if existing:
        flash("You already reviewed this analysis.", "info")
        return redirect(url_for("analysis.index", match_id=analysis.match_id))

    toss_val = request.form.get("toss_accurate")
    score_val = request.form.get("score_accurate")

    rating_value = request.form.get("rating", type=int)
    if rating_value not in {1, 2, 3, 4, 5}:
        flash("Choose a rating from 1 to 5 before submitting feedback.", "error")
        return redirect(url_for("analysis.result", match_id=analysis.match_id))

    review = Review(
        analysis_id=analysis_id,
        user_id=current_user.id,
        overall_rating=rating_value,
        toss_accurate=True if toss_val == "true" else (False if toss_val == "false" else None),
        score_accurate=True if score_val == "true" else (False if score_val == "false" else None),
        comments=request.form.get("comments", "").strip() or None,
    )
    db.session.add(review)
    db.session.commit()

    flash("Review submitted!", "success")
    return redirect(url_for("analysis.result", match_id=analysis.match_id))
