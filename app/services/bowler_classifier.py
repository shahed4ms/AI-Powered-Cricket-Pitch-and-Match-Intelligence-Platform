import json
from pathlib import Path


STYLE_FILE = (
    Path(__file__).resolve().parents[2]
    / "data"
    / "player_bowling_styles.json"
)


VALID_STYLES = {
    "fast",
    "medium",
    "off_spin",
    "leg_spin"
}


def load_player_styles():

    if not STYLE_FILE.exists():
        return {}

    try:

        with STYLE_FILE.open(
            "r",
            encoding="utf-8"
        ) as file:

            data = json.load(file)

            if isinstance(data, dict):
                return data

    except (
        OSError,
        json.JSONDecodeError
    ):

        return {}

    return {}


def classify_bowler(player_name):

    if not player_name:
        return "unknown"

    styles = load_player_styles()

    player = styles.get(
        player_name
    )

    if not player:
        return "unknown"

    if isinstance(player, str):

        style = player.lower().strip()

    elif isinstance(player, dict):

        style = str(
            player.get(
                "type",
                ""
            )
        ).lower().strip()

    else:

        return "unknown"

    if style in VALID_STYLES:
        return style

    return "unknown"