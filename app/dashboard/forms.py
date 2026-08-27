from flask_wtf import FlaskForm
from flask_wtf.file import FileField, FileAllowed
from wtforms import StringField, SelectField, DateField, TimeField, HiddenField
from wtforms.validators import DataRequired, Optional
from datetime import date


class MatchForm(FlaskForm):
    match_name = StringField("Match Name", validators=[DataRequired()])
    venue_id = HiddenField("Venue ID", validators=[DataRequired()])
    venue_search = StringField("Venue", validators=[DataRequired()])
    format = SelectField(
        "Game Format",
        choices=[("Test", "Test"), ("ODI", "ODI"), ("T20", "T20"), ("Custom", "Custom")],
        validators=[DataRequired()],
    )
    date_start = DateField("Date", validators=[DataRequired()], default=date.today)
    date_end = DateField("End Date", validators=[Optional()])
    time_start = TimeField("Start Time", validators=[Optional()])
    time_end = TimeField("End Time", validators=[Optional()])
    ball_type = SelectField(
        "Ball Type",
        choices=[("", "Optional"), ("white", "White Ball"), ("red", "Red Ball"), ("pink", "Pink Ball"), ("other", "Other")],
        validators=[Optional()],
    )
    pitch_image = FileField(
        "Pitch Image",
        validators=[Optional(), FileAllowed(["jpg", "jpeg", "png"], "Images only (JPG, PNG)")],
    )
