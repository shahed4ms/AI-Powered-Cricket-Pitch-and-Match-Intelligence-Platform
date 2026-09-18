from flask import current_app, render_template, redirect, url_for, flash, request
from flask_login import login_user, logout_user, login_required, current_user
from flask_dance.contrib.google import google
from app.auth import auth_bp
from app.auth.forms import LoginForm, SignupForm
from app.extensions import db, limiter
from app.models import User


@auth_bp.route("/login", methods=["GET", "POST"])
@limiter.limit("20/minute", methods=["POST"])
def login():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = LoginForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        user = User.query.filter(db.func.lower(User.email) == email).first()
        if user and user.check_password(form.password.data):
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get("next")
            flash("Logged in successfully!", "success")
            return redirect(next_page or url_for("dashboard.index"))
        flash("Invalid email or password.", "error")

    return render_template("auth/login.html", form=form)


@auth_bp.route("/signup", methods=["GET", "POST"])
@limiter.limit("10/minute")
def signup():
    if current_user.is_authenticated:
        return redirect(url_for("dashboard.index"))

    form = SignupForm()
    if form.validate_on_submit():
        email = (form.email.data or "").strip().lower()
        user = User(email=email, username=form.username.data.strip())
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Account created successfully!", "success")
        return redirect(url_for("dashboard.index"))

    return render_template("auth/signup.html", form=form)


@auth_bp.route("/google")
def google_login():
    if not current_app.config.get("GOOGLE_OAUTH_CLIENT_ID") or not current_app.config.get(
        "GOOGLE_OAUTH_CLIENT_SECRET"
    ):
        flash("Google login is not configured for this local app yet.", "info")
        return redirect(url_for("auth.login"))

    if not google.authorized:
        return redirect(url_for("google.login"))

    resp = google.get("/oauth2/v2/userinfo")
    if resp.ok:
        google_data = resp.json()
        user = User.query.filter_by(google_id=google_data["id"]).first()
        if not user:
            user = User.query.filter_by(email=google_data["email"]).first()
            if user:
                user.google_id = google_data["id"]
                user.avatar_url = google_data.get("picture")
            else:
                user = User(
                    email=google_data["email"],
                    username=google_data.get("name", google_data["email"].split("@")[0]),
                    google_id=google_data["id"],
                    avatar_url=google_data.get("picture"),
                )
                db.session.add(user)
        db.session.commit()
        login_user(user)
        flash("Logged in with Google!", "success")
    else:
        flash("Google login failed.", "error")

    return redirect(url_for("dashboard.index"))


@auth_bp.route("/logout")
@login_required
def logout():
    logout_user()
    flash("Logged out.", "info")
    return redirect(url_for("auth.login"))
