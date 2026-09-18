import os
from io import BytesIO
from datetime import datetime, timedelta
from flask import current_app, render_template, redirect, url_for, flash, jsonify, request, send_file
from flask_login import login_required, current_user
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.platypus import Paragraph, SimpleDocTemplate, Spacer, Table, TableStyle
from app.analysis import analysis_bp
from app.extensions import db, limiter
from app.models import Match, Analysis, Review, Venue
from app.services import weather_service, venue_service, pitch_analyzer, ai_suggestions


@analysis_bp.errorhandler(429)
def analysis_rate_limit_error(error):
    return jsonify({"error": "Analysis is being generated too often. Please wait a moment and try again."}), 429


def _build_review_questions(analysis):
    suggestions = analysis.ai_suggestions or {}
    questions = []
    if suggestions.get("toss_suggestion"):
        questions.append(("toss_prediction", "Was the AI toss recommendation correct?"))
    if suggestions.get("score_prediction"):
        questions.append(("score_prediction", "Did the final scores fall within the AI prediction ranges?"))
    if suggestions.get("dew_factor"):
        questions.append(("dew_prediction", "Was the AI dew or conditions prediction accurate?"))
    if suggestions.get("bowling_strategy") or suggestions.get("batting_strategy"):
        questions.append(("strategy_prediction", "Were the AI strategy suggestions useful during the match?"))
    return questions


@analysis_bp.route("/<int:match_id>", methods=["GET"])
@login_required
def index(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        flash("Unauthorized access.", "error")
        return redirect(url_for("dashboard.index"))

    venue = Venue.query.get(match.venue_id)
    analysis = Analysis.query.filter_by(match_id=match.id).first()
    if analysis and analysis.weather_data and "confidence" not in analysis.weather_data:
        analysis.weather_data = weather_service.enrich_weather_data(analysis.weather_data)
        db.session.commit()
    if analysis and venue:
        current_venue_stats = venue_service.get_venue_stats(match.venue_id, match.format)
        if current_venue_stats and analysis.venue_stats != current_venue_stats:
            analysis.venue_stats = current_venue_stats
            db.session.commit()
    if analysis and venue and match.time_start:
        stored_hourly = (analysis.weather_data or {}).get("hourly", [])
        expected_date_end = _weather_date_end(match).isoformat()
        stored_date_end = (analysis.weather_data or {}).get("date_end")
        if len(stored_hourly) < 7 or (not match.date_end and len(stored_hourly) != 7) or stored_date_end != expected_date_end:
            refreshed_weather = _fetch_match_weather(match, venue)
            if refreshed_weather and not refreshed_weather.get("error"):
                analysis.weather_data = refreshed_weather
                db.session.commit()
    review = Review.query.filter_by(analysis_id=analysis.id).first() if analysis else None

    return render_template("analysis.html", match=match, venue=venue, analysis=analysis, review=review)


@analysis_bp.route("/<int:match_id>/download", methods=["GET"])
@login_required
def download_analysis(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    venue = Venue.query.get(match.venue_id)
    analysis = Analysis.query.filter_by(match_id=match.id).first()
    if not analysis:
        flash("Generate the analysis before downloading it.", "error")
        return redirect(url_for("analysis.index", match_id=match.id))

    styles = getSampleStyleSheet()
    buffer = BytesIO()
    document = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=0.65 * inch, leftMargin=0.65 * inch)
    story = [Paragraph("PitchVisionAI Match Analysis", styles["Title"]), Spacer(1, 0.15 * inch)]
    story.extend([
        Paragraph(match.match_name, styles["Heading2"]),
        Paragraph(f"{match.format} | {venue.name if venue else 'Unknown venue'} | {match.date_start}", styles["BodyText"]),
        Spacer(1, 0.2 * inch),
    ])

    def add_section(title, rows):
        story.append(Paragraph(title, styles["Heading2"]))
        table = Table([[str(label), str(value)] for label, value in rows], colWidths=[2.1 * inch, 4.8 * inch])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#eeeeee")),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#bbbbbb")),
            ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ("PADDING", (0, 0), (-1, -1), 6),
        ]))
        story.extend([table, Spacer(1, 0.18 * inch)])

    stats = (analysis.venue_stats or {}).get("historical", analysis.venue_stats or {})
    scores = stats.get("scores", {})
    first = scores.get("first_innings", {})
    second = scores.get("second_innings", {})
    add_section("Venue Statistics", [
        ("Batting first win", f"{(stats.get('batting_first') or {}).get('win_percentage', '--')}%"),
        ("Bowling first win", f"{(stats.get('bowling_first') or {}).get('win_percentage', '--')}%"),
        ("1st innings average / min / max", f"{first.get('average', '--')} / {first.get('minimum', '--')} / {first.get('maximum', '--')}"),
        ("2nd innings average / min / max", f"{second.get('average', '--')} / {second.get('minimum', '--')} / {second.get('maximum', '--')}"),
    ])

    predictions = analysis.ai_suggestions or {}
    toss = predictions.get("toss_suggestion") or {}
    score = predictions.get("score_prediction") or {}
    add_section("AI Predictions", [
        ("Toss recommendation", toss.get("decision", "--")),
        ("Toss reasoning", toss.get("reasoning", "--")),
        ("1st innings prediction", f"{(score.get('first_innings') or {}).get('low', '--')} - {(score.get('first_innings') or {}).get('high', '--')}"),
        ("2nd innings prediction", f"{(score.get('second_innings') or {}).get('low', '--')} - {(score.get('second_innings') or {}).get('high', '--')}"),
    ])

    if analysis.key_insights:
        add_section("Key Insights", [(f"Insight {index}", insight) for index, insight in enumerate(analysis.key_insights, 1)])

    document.build(story)
    buffer.seek(0)
    filename = f"{match.match_name.replace(' ', '_')}_analysis.pdf"
    return send_file(buffer, as_attachment=True, download_name=filename, mimetype="application/pdf")

@analysis_bp.route("/<int:match_id>/generate", methods=["POST"])
@login_required
@limiter.limit("20/minute")
def generate(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    venue = Venue.query.get(match.venue_id)

    warnings = []
    weather_data = None
    if venue:
        weather_data = _fetch_match_weather(match, venue)
        if weather_data and weather_data.get("error"):
            warnings.append(weather_data["error"])
        else:
            weather_data = weather_service.enrich_weather_data(weather_data)

    pitch_analysis = None
    if match.pitch_image_path:
        image_path = os.path.join(current_app.config["UPLOAD_FOLDER"], os.path.basename(match.pitch_image_path))
        if os.path.exists(image_path):
            try:
                pitch_analysis = pitch_analyzer.analyze_pitch_image(image_path)
            except Exception as exc:
                current_app.logger.exception("Pitch analysis pipeline failed: %s", exc.__class__.__name__)
                pitch_analysis = {"error": "Pitch analysis failed."}
            if pitch_analysis and pitch_analysis.get("error"):
                warnings.append(pitch_analysis["error"])
        else:
            pitch_analysis = {"error": "Pitch image could not be found. Upload it again and retry."}
            warnings.append(pitch_analysis["error"])

    venue_stats = venue_service.get_venue_stats(
    match.venue_id,
    match.format
)
    feedback = Review.query.join(Analysis, Review.analysis_id == Analysis.id).join(
        Match, Analysis.match_id == Match.id
    ).filter(Match.venue_id == match.venue_id, Match.format == match.format).all()
    if venue_stats and feedback:
        venue_stats["feedback_summary"] = {
            "reviews": len(feedback),
            "average_rating": round(sum(item.overall_rating or 0 for item in feedback) / len(feedback), 2),
            "toss_accuracy_reports": sum(item.toss_accurate is not None for item in feedback),
            "toss_correct_reports": sum(item.toss_accurate is True for item in feedback),
            "score_accuracy_reports": sum(item.score_accurate is not None for item in feedback),
            "score_correct_reports": sum(item.score_accurate is True for item in feedback),
        }

    match_context = {
        "match_name": match.match_name,
        "format": match.format,
        "ball_type": match.ball_type or "Standard",
        "time_start": str(match.time_start) if match.time_start else "N/A",
        "time_end": str(match.time_end) if match.time_end else "N/A",
        "date_start": match.date_start.isoformat() if match.date_start else "N/A",
        "date_end": match.date_end.isoformat() if match.date_end else None,
        "venue": venue.to_dict() if venue else None,
    }

    try:
        suggestions = ai_suggestions.generate_suggestions(match_context, weather_data, pitch_analysis, venue_stats)
    except Exception as exc:
        current_app.logger.exception("Analysis provider pipeline failed: %s", exc.__class__.__name__)
        suggestions = {"error": "Analysis provider failed."}

    if not suggestions:
        suggestions = {"error": "Analysis provider returned no result."}

    if suggestions and suggestions.get("error"):
        warnings.append(suggestions["error"])
        suggestions = ai_suggestions.build_fallback_suggestions(
            match_context,
            weather_data,
            pitch_analysis,
            venue_stats,
            reason=suggestions["error"],
        )
    if warnings:
        suggestions["warnings"] = warnings

    analysis = Analysis.query.filter_by(match_id=match.id).first()
    if not analysis:
        analysis = Analysis(match_id=match.id)
        db.session.add(analysis)

    analysis.weather_data = weather_data
    analysis.pitch_analysis = pitch_analysis
    analysis.venue_stats = venue_stats
    analysis.ai_suggestions = suggestions

    if suggestions and "error" not in suggestions:
        toss = suggestions.get("toss_suggestion", {})
        analysis.toss_suggestion = toss.get("decision")
        analysis.toss_reasoning = toss.get("reasoning")

        score = suggestions.get("score_prediction", {})
        fi = score.get("first_innings", {})
        si = score.get("second_innings", {})
        analysis.score_first_innings = f"{fi.get('low', '?')}-{fi.get('high', '?')}"
        analysis.score_second_innings = f"{si.get('low', '?')}-{si.get('high', '?')}"

        dew = suggestions.get("dew_factor", {})
        analysis.dew_expected = dew.get("expected")
        analysis.dew_timing = dew.get("timing")

        analysis.key_insights = suggestions.get("key_insights", [])

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()
        current_app.logger.exception("Analysis results could not be saved")
        return jsonify({"error": "Analysis results could not be saved. Please try again."}), 500

    return jsonify({
        "success": True,
        "analysis_id": analysis.id,
        "source": suggestions.get("source", "openai"),
        "warnings": warnings,
    })


def _fetch_match_weather(match, venue):
    if venue.latitude is None or venue.longitude is None:
        search_term = venue.city or venue.name
        geocoded = venue_service.search_city_geocoding(search_term)
        if geocoded:
            venue.latitude = geocoded[0].get("latitude")
            venue.longitude = geocoded[0].get("longitude")
            db.session.commit()

    if venue.latitude is None or venue.longitude is None:
        return {"error": "Weather coordinates are unavailable for this venue", "provider": "open_meteo"}

    weather_end = match.time_end
    weather_date_end = _weather_date_end(match) if match.time_start else match.date_end
    if match.time_start:
        end_datetime = datetime.combine(match.date_start, match.time_start) + timedelta(hours=6)
        weather_end = end_datetime.time()
    weather_data = weather_service.get_weather_forecast(
        float(venue.latitude), float(venue.longitude),
        match.date_start, match.time_start, weather_end, weather_date_end,
        continuous=bool(match.time_start and not match.date_end),
    )
    if weather_data and not weather_data.get("error"):
        return weather_service.enrich_weather_data(weather_data)
    return weather_data


def _weather_date_end(match):
    if match.date_end:
        return match.date_end
    if match.time_start:
        return (datetime.combine(match.date_start, match.time_start) + timedelta(hours=6)).date()
    return match.date_start


@analysis_bp.route("/<int:match_id>/result", methods=["POST"])
@login_required
def save_result(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    status = request.form.get("status", "completed")
    if status == "skipped":
        analyses = Analysis.query.filter_by(match_id=match.id).all()
        for analysis in analyses:
            Review.query.filter_by(analysis_id=analysis.id).delete(synchronize_session=False)
            db.session.delete(analysis)
        db.session.delete(match)
        db.session.commit()
        flash("Match deleted.", "success")
        return redirect(url_for("dashboard.index"))
    elif status == "completed":
        outcome = request.form.get("outcome")
        if outcome not in {"won", "lost", "draw"}:
            flash("Choose the match result before saving.", "error")
            return redirect(url_for("analysis.result", match_id=match.id))
        match.result_status = "completed"
        match.result_outcome = outcome
        match.toss_outcome = request.form.get("toss_outcome") or None
        match.batting_innings = request.form.get("batting_innings") or None
        match.own_score = request.form.get("own_score", "").strip() or None
        match.opponent_score = request.form.get("opponent_score", "").strip() or None
        match.toss_decision = request.form.get("toss_decision") or None
        match.batting_first_team = request.form.get("batting_first_team", "").strip() or None
        match.innings_first_score = request.form.get("innings_first_score", "").strip() or None
        match.innings_second_score = request.form.get("innings_second_score", "").strip() or None
    else:
        return jsonify({"error": "Invalid result status"}), 400

    db.session.commit()
    flash("Match result saved." if status == "completed" else "Saved as a dummy match.", "success")
    return redirect(url_for("analysis.result", match_id=match.id))


@analysis_bp.route("/<int:match_id>/result", methods=["GET"])
@login_required
def result(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        flash("Unauthorized access.", "error")
        return redirect(url_for("dashboard.index"))
    analysis = Analysis.query.filter_by(match_id=match.id).first()
    review = Review.query.filter_by(analysis_id=analysis.id).first() if analysis else None
    return render_template("result.html", match=match, analysis=analysis, review=review)


@analysis_bp.route("/<int:match_id>/review", methods=["GET", "POST"])
@login_required
def review(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        flash("Unauthorized access.", "error")
        return redirect(url_for("dashboard.index"))

    analysis = Analysis.query.filter_by(match_id=match.id).first()
    if not analysis:
        flash("Generate the analysis before reviewing it.", "error")
        return redirect(url_for("analysis.index", match_id=match.id))

    existing = Review.query.filter_by(analysis_id=analysis.id, user_id=current_user.id).first()
    questions = _build_review_questions(analysis)
    if request.method == "POST":
        rating = request.form.get("rating", type=int)
        if rating not in {1, 2, 3, 4, 5}:
            flash("Choose an overall rating from 1 to 5.", "error")
            return render_template("review.html", match=match, analysis=analysis, review=existing, questions=questions)

        values = {
            "toss_winner": request.form.get("toss_winner"),
            "innings_order": request.form.get("innings_order"),
            "team_score": request.form.get("team_score", "").strip(),
            "opponent_score": request.form.get("opponent_score", "").strip(),
            "team_first_innings_score": request.form.get("team_first_innings_score", "").strip(),
            "opponent_first_innings_score": request.form.get("opponent_first_innings_score", "").strip(),
            "team_second_innings_score": request.form.get("team_second_innings_score", "").strip(),
            "opponent_second_innings_score": request.form.get("opponent_second_innings_score", "").strip(),
            "match_winner": request.form.get("match_winner"),
            "custom_answers": {
                key: request.form.get(f"custom_{key}") for key, _ in questions
            },
        }
        if existing:
            review_record = existing
        else:
            review_record = Review(analysis_id=analysis.id, user_id=current_user.id)
            db.session.add(review_record)
        review_record.overall_rating = rating
        custom_answers = values["custom_answers"]
        review_record.toss_accurate = custom_answers.get("toss_prediction") == "yes" if custom_answers.get("toss_prediction") else None
        review_record.score_accurate = custom_answers.get("score_prediction") == "yes" if custom_answers.get("score_prediction") else None
        review_record.comments = request.form.get("comments", "").strip() or None
        review_record.review_data = values
        match.result_status = "completed"
        match.result_outcome = {
            "you": "won",
            "opponent": "lost",
            "draw": "draw",
        }.get(values["match_winner"])
        match.toss_outcome = "won" if values["toss_winner"] == "you" else "lost"
        match.batting_innings = "first" if values["innings_order"] == "bat_first" else "second"
        if match.format == "Test":
            match.innings_first_score = f"{values['team_first_innings_score']} / {values['opponent_first_innings_score']}"
            match.innings_second_score = f"{values['team_second_innings_score']} / {values['opponent_second_innings_score']}"
            match.own_score = values["team_second_innings_score"]
            match.opponent_score = values["opponent_second_innings_score"]
        else:
            match.own_score = values["team_score"]
            match.opponent_score = values["opponent_score"]
        db.session.commit()
        flash("Review saved. Your match record has been updated.", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("review.html", match=match, analysis=analysis, review=existing, questions=questions)


@analysis_bp.route("/<int:match_id>/chat", methods=["POST"])
@login_required
@limiter.limit("20/minute")
def chat(match_id):
    match = Match.query.get_or_404(match_id)
    if match.user_id != current_user.id:
        return jsonify({"error": "Unauthorized"}), 403

    analysis = Analysis.query.filter_by(match_id=match.id).first()
    if not analysis:
        return jsonify({"error": "Generate the match analysis before starting a chat."}), 400

    payload = request.get_json(silent=True) or {}
    question = str(payload.get("message") or "").strip()
    if not question:
        return jsonify({"error": "Ask a strategy question first."}), 400
    if len(question) > 2000:
        return jsonify({"error": "Keep your question under 2,000 characters."}), 400

    venue = Venue.query.get(match.venue_id)
    match_context = {
        "match_name": match.match_name,
        "format": match.format,
        "ball_type": match.ball_type or "Standard",
        "date_start": match.date_start.isoformat() if match.date_start else None,
        "date_end": match.date_end.isoformat() if match.date_end else None,
        "time_start": str(match.time_start) if match.time_start else None,
        "time_end": str(match.time_end) if match.time_end else None,
        "venue": venue.to_dict() if venue else None,
    }
    analysis_context = {
        "weather": analysis.weather_data,
        "pitch": analysis.pitch_analysis,
        "venue_stats": analysis.venue_stats,
        "predictions": analysis.ai_suggestions,
    }
    result = ai_suggestions.generate_chat_response(
        match_context, analysis_context, question, payload.get("history")
    )
    return jsonify(result)


@analysis_bp.route("/api/weather", methods=["GET"])
@login_required
def get_weather():
    venue_id = request.args.get("venue_id")
    date_str = request.args.get("date")
    time_start = request.args.get("time_start")
    time_end = request.args.get("time_end")

    if not venue_id or not date_str:
        return jsonify({"error": "venue_id and date required"}), 400

    venue = Venue.query.get(int(venue_id))
    if not venue or not venue.latitude:
        return jsonify({"error": "Venue not found or no coordinates"}), 404

    from datetime import time as dt_time
    ts = None
    te = None
    if time_start:
        parts = time_start.split(":")
        ts = dt_time(int(parts[0]), int(parts[1]))
    if time_end:
        parts = time_end.split(":")
        te = dt_time(int(parts[0]), int(parts[1]))

    from datetime import date as dt_date
    d = dt_date.fromisoformat(date_str)

    data = weather_service.get_weather_forecast(float(venue.latitude), float(venue.longitude), d, ts, te)
    if not data or data.get("error"):
        return jsonify({"error": (data or {}).get("error", "Weather data unavailable")}), 502
    data = weather_service.enrich_weather_data(data)

    return jsonify(data)
