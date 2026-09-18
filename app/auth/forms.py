from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, SubmitField, BooleanField
from wtforms.validators import DataRequired, Email, Length, EqualTo, ValidationError
from app.extensions import db
from app.models import User


class LoginForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    password = PasswordField("Password", validators=[DataRequired()])
    remember_me = BooleanField("Remember Me")
    submit = SubmitField("Login")


class SignupForm(FlaskForm):
    email = StringField("Email", validators=[DataRequired(), Email()])
    username = StringField("Username", validators=[DataRequired(), Length(min=3, max=100)])
    password = PasswordField("Password", validators=[DataRequired(), Length(min=6)])
    confirm_password = PasswordField(
        "Confirm Password", validators=[DataRequired(), EqualTo("password", message="Passwords must match")]
    )
    submit = SubmitField("Sign Up")

    def validate_email(self, field):
        email = (field.data or "").strip().lower()
        if User.query.filter(db.func.lower(User.email) == email).first():
            raise ValidationError("Email already registered.")

    def validate_username(self, field):
        username = (field.data or "").strip()
        if User.query.filter_by(username=username).first():
            raise ValidationError("Username already taken.")
