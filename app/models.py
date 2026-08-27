# ============================================================
# VENUE FORMAT HISTORICAL STATISTICS
# ============================================================
from datetime import datetime

from app.extensions import db
from flask_login import UserMixin
from werkzeug.security import check_password_hash, generate_password_hash


class User(UserMixin, db.Model):
    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True)
    email = db.Column(db.String(255), nullable=False, unique=True)
    username = db.Column(db.String(100), nullable=False)
    password_hash = db.Column(db.String(255))
    google_id = db.Column(db.String(255), unique=True)
    avatar_url = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    time_format = db.Column(db.String(10), default="24h")
    temperature_unit = db.Column(db.String(2), default="C")

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return bool(self.password_hash) and check_password_hash(self.password_hash, password)


class Venue(db.Model):
    __tablename__ = "venues"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(255), nullable=False)
    city = db.Column(db.String(100), nullable=False)
    country = db.Column(db.String(100), nullable=False)
    latitude = db.Column(db.Numeric(10, 7))
    longitude = db.Column(db.Numeric(10, 7))
    pitch_type = db.Column(db.String(50))
    batting_first_win_pct = db.Column(db.Numeric(5, 2))
    batting_second_win_pct = db.Column(db.Numeric(5, 2))
    highest_score = db.Column(db.String(20))
    lowest_score = db.Column(db.String(20))
    avg_score = db.Column(db.Numeric(6, 2))
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    def to_dict(self):
        return {
            "id": self.id,
            "name": self.name,
            "city": self.city,
            "country": self.country,
            "latitude": float(self.latitude) if self.latitude is not None else None,
            "longitude": float(self.longitude) if self.longitude is not None else None,
            "pitch_type": self.pitch_type,
            "batting_first_win_pct": float(self.batting_first_win_pct) if self.batting_first_win_pct is not None else None,
            "batting_second_win_pct": float(self.batting_second_win_pct) if self.batting_second_win_pct is not None else None,
            "highest_score": self.highest_score,
            "lowest_score": self.lowest_score,
            "avg_score": float(self.avg_score) if self.avg_score is not None else None,
        }


class Match(db.Model):
    __tablename__ = "matches"

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    venue_id = db.Column(db.Integer, db.ForeignKey("venues.id"), nullable=False)
    match_name = db.Column(db.String(255), nullable=False)
    format = db.Column(db.String(20), nullable=False)
    date_start = db.Column(db.Date, nullable=False)
    date_end = db.Column(db.Date)
    time_start = db.Column(db.Time)
    time_end = db.Column(db.Time)
    ball_type = db.Column(db.String(20))
    pitch_image_path = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    result_status = db.Column(db.String(20), default="pending")
    result_outcome = db.Column(db.String(20))
    toss_decision = db.Column(db.String(20))
    batting_first_team = db.Column(db.String(255))
    innings_first_score = db.Column(db.String(30))
    innings_second_score = db.Column(db.String(30))
    toss_outcome = db.Column(db.String(10))
    batting_innings = db.Column(db.String(10))
    own_score = db.Column(db.String(30))
    opponent_score = db.Column(db.String(30))

    venue = db.relationship("Venue", foreign_keys=[venue_id])
    user = db.relationship("User", foreign_keys=[user_id])


class Analysis(db.Model):
    __tablename__ = "analyses"

    id = db.Column(db.Integer, primary_key=True)
    match_id = db.Column(db.Integer, db.ForeignKey("matches.id"), nullable=False)
    weather_data = db.Column(db.JSON)
    pitch_analysis = db.Column(db.JSON)
    venue_stats = db.Column(db.JSON)
    ai_suggestions = db.Column(db.JSON)
    toss_suggestion = db.Column(db.String(50))
    toss_reasoning = db.Column(db.Text)
    score_first_innings = db.Column(db.String(30))
    score_second_innings = db.Column(db.String(30))
    dew_expected = db.Column(db.Boolean)
    dew_timing = db.Column(db.String(50))
    key_insights = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    match = db.relationship("Match", foreign_keys=[match_id])


class Review(db.Model):
    __tablename__ = "reviews"

    id = db.Column(db.Integer, primary_key=True)
    analysis_id = db.Column(db.Integer, db.ForeignKey("analyses.id"), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey("users.id"), nullable=False)
    overall_rating = db.Column(db.Integer)
    toss_accurate = db.Column(db.Boolean)
    score_accurate = db.Column(db.Boolean)
    comments = db.Column(db.Text)
    review_data = db.Column(db.JSON)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    analysis = db.relationship("Analysis", foreign_keys=[analysis_id])
    user = db.relationship("User", foreign_keys=[user_id])

class VenueFormatStats(db.Model):
    """
    Historical cricket statistics grouped by:

        Venue + Format

    Examples:

        Wankhede Stadium + T20
        Wankhede Stadium + ODI
        Wankhede Stadium + Test
    """

    __tablename__ = "venue_format_stats"

    id = db.Column(
        db.Integer,
        primary_key=True
    )

    venue_id = db.Column(
        db.Integer,
        db.ForeignKey("venues.id"),
        nullable=False,
        index=True
    )

    format = db.Column(
        db.String(20),
        nullable=False,
        index=True
    )

    # ========================================================
    # MATCH INFORMATION
    # ========================================================

    matches = db.Column(
        db.Integer,
        default=0
    )

    completed_matches = db.Column(
        db.Integer,
        default=0
    )

    no_results = db.Column(
        db.Integer,
        default=0
    )

    ties = db.Column(
        db.Integer,
        default=0
    )

    draws = db.Column(
        db.Integer,
        default=0
    )

    # ========================================================
    # BAT FIRST / BOWL FIRST
    # ========================================================

    batting_first_matches = db.Column(
        db.Integer,
        default=0
    )

    batting_first_wins = db.Column(
        db.Integer,
        default=0
    )

    batting_first_win_pct = db.Column(
        db.Float,
        default=0.0
    )

    bowling_first_matches = db.Column(
        db.Integer,
        default=0
    )

    bowling_first_wins = db.Column(
        db.Integer,
        default=0
    )

    bowling_first_win_pct = db.Column(
        db.Float,
        default=0.0
    )

    # ========================================================
    # ALL INNINGS SCORES
    # ========================================================

    innings_count = db.Column(
        db.Integer,
        default=0
    )

    total_runs = db.Column(
        db.Integer,
        default=0
    )

    avg_score = db.Column(
        db.Float,
        default=0.0
    )

    max_score = db.Column(
        db.Integer,
        default=0
    )

    min_score = db.Column(
        db.Integer
    )

    # ========================================================
    # FIRST INNINGS
    # ========================================================

    first_innings_count = db.Column(
        db.Integer,
        default=0
    )

    first_innings_total_runs = db.Column(
        db.Integer,
        default=0
    )

    avg_first_innings_score = db.Column(
        db.Float,
        default=0.0
    )

    max_first_innings_score = db.Column(
        db.Integer,
        default=0
    )

    min_first_innings_score = db.Column(
        db.Integer
    )

    # ========================================================
    # SECOND INNINGS
    # ========================================================

    second_innings_count = db.Column(
        db.Integer,
        default=0
    )

    second_innings_total_runs = db.Column(
        db.Integer,
        default=0
    )

    avg_second_innings_score = db.Column(
        db.Float,
        default=0.0
    )

    max_second_innings_score = db.Column(
        db.Integer,
        default=0
    )

    min_second_innings_score = db.Column(
        db.Integer
    )

    # ========================================================
    # WICKETS
    # ========================================================

    total_bowler_wickets = db.Column(
        db.Integer,
        default=0
    )

    fast_wickets = db.Column(
        db.Integer,
        default=0
    )

    medium_wickets = db.Column(
        db.Integer,
        default=0
    )

    off_spin_wickets = db.Column(
        db.Integer,
        default=0
    )

    leg_spin_wickets = db.Column(
        db.Integer,
        default=0
    )

    unknown_wickets = db.Column(
        db.Integer,
        default=0
    )

    # ========================================================
    # WICKET %
    # ========================================================

    fast_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    medium_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    off_spin_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    leg_spin_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    pace_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    spin_wicket_pct = db.Column(
        db.Float,
        default=0.0
    )

    # ========================================================
    # METADATA
    # ========================================================

    data_source = db.Column(
        db.String(100),
        default="Cricsheet"
    )

    updated_at = db.Column(
        db.DateTime,
        default=datetime.utcnow,
        onupdate=datetime.utcnow
    )

    # ========================================================
    # UNIQUE VENUE + FORMAT
    # ========================================================

    __table_args__ = (
        db.UniqueConstraint(
            "venue_id",
            "format",
            name="uq_venue_format_stats"
        ),
    )

    def to_dict(self):

        return {
            "id": self.id,
            "venue_id": self.venue_id,
            "format": self.format,

            "matches": self.matches,
            "completed_matches": self.completed_matches,
            "no_results": self.no_results,
            "ties": self.ties,
            "draws": self.draws,

            "batting_first": {
                "matches": self.batting_first_matches,
                "wins": self.batting_first_wins,
                "win_percentage": self.batting_first_win_pct
            },

            "bowling_first": {
                "matches": self.bowling_first_matches,
                "wins": self.bowling_first_wins,
                "win_percentage": self.bowling_first_win_pct
            },

            "scores": {
                "all_innings": {
                    "count": self.innings_count,
                    "average": self.avg_score,
                    "maximum": self.max_score,
                    "minimum": self.min_score
                },

                "first_innings": {
                    "count": self.first_innings_count,
                    "average": self.avg_first_innings_score,
                    "maximum": self.max_first_innings_score,
                    "minimum": self.min_first_innings_score
                },

                "second_innings": {
                    "count": self.second_innings_count,
                    "average": self.avg_second_innings_score,
                    "maximum": self.max_second_innings_score,
                    "minimum": self.min_second_innings_score
                }
            },

            "wickets": {
                "total": self.total_bowler_wickets,

                "fast": {
                    "count": self.fast_wickets,
                    "percentage": self.fast_wicket_pct
                },

                "medium": {
                    "count": self.medium_wickets,
                    "percentage": self.medium_wicket_pct
                },

                "off_spin": {
                    "count": self.off_spin_wickets,
                    "percentage": self.off_spin_wicket_pct
                },

                "leg_spin": {
                    "count": self.leg_spin_wickets,
                    "percentage": self.leg_spin_wicket_pct
                },

                "pace_percentage": self.pace_wicket_pct,

                "spin_percentage": self.spin_wicket_pct,

                "unknown": self.unknown_wickets
            },

            "data_source": self.data_source,

            "updated_at": (
                self.updated_at.isoformat()
                if self.updated_at
                else None
            )
        }