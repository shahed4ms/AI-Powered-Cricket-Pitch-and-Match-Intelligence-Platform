import json
import re
from collections import defaultdict
from pathlib import Path

from app.extensions import db
from app.models import Venue, VenueFormatStats

from app.services.bowler_classifier import (
    classify_bowler
)


SUPPORTED_FORMATS = {
    "T20": "T20",
    "IT20": "T20",
    "ODI": "ODI",
    "Test": "Test"
}


BOWLER_WICKET_TYPES = {
    "bowled",
    "caught",
    "caught and bowled",
    "lbw",
    "stumped",
    "hit wicket"
}


def load_venue_aliases():

    path = (
        Path(__file__).resolve().parents[2]
        / "data"
        / "venue_aliases.json"
    )

    if not path.exists():
        return {}

    try:

        with path.open(
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

        pass

    return {}


VENUE_ALIASES = load_venue_aliases()


def normalize_venue_name(name):

    if not name:
        return "Unknown Venue"

    name = str(name).strip()

    name = re.sub(
        r"\s+",
        " ",
        name
    )

    return VENUE_ALIASES.get(
        name,
        name
    )


def normalize_format(match_type):

    if not match_type:
        return None

    return SUPPORTED_FORMATS.get(
        str(match_type).strip()
    )


def load_json_files(data_directory):

    directory = Path(
        data_directory
    )

    if not directory.exists():

        raise FileNotFoundError(
            f"JSON directory does not exist: "
            f"{directory}"
        )

    files = sorted(
        directory.glob("*.json")
    )

    print(
        f"Found {len(files)} JSON files."
    )

    for file_path in files:

        try:

            with file_path.open(
                "r",
                encoding="utf-8"
            ) as file:

                data = json.load(file)

            yield file_path, data

        except Exception as error:

            print(
                f"[SKIP] "
                f"{file_path.name}: "
                f"{error}"
            )


def get_match_metadata(data):

    info = data.get(
        "info",
        {}
    )

    return {
        "venue": normalize_venue_name(
            info.get("venue")
        ),

        "city": (
            info.get("city")
            or "Unknown"
        ),

        "format": normalize_format(
            info.get("match_type")
        ),

        "teams": info.get(
            "teams",
            []
        ),

        "outcome": info.get(
            "outcome",
            {}
        ),

        "toss": info.get(
            "toss",
            {}
        )
    }


def calculate_innings_score(innings):

    total = 0

    for over in innings.get(
        "overs",
        []
    ):

        for delivery in over.get(
            "deliveries",
            []
        ):

            runs = delivery.get(
                "runs",
                {}
            )

            total += int(
                runs.get(
                    "total",
                    0
                )
            )

    return total


def get_wickets(innings):

    wickets = []

    for over in innings.get(
        "overs",
        []
    ):

        for delivery in over.get(
            "deliveries",
            []
        ):

            bowler = delivery.get(
                "bowler"
            )

            for wicket in delivery.get(
                "wickets",
                []
            ):

                wickets.append({
                    "bowler": bowler,

                    "kind": wicket.get(
                        "kind"
                    ),

                    "player_out": wicket.get(
                        "player_out"
                    )
                })

    return wickets


def is_bowler_wicket(kind):

    if not kind:
        return False

    return (
        str(kind).lower().strip()
        in BOWLER_WICKET_TYPES
    )


def determine_result(data):

    info = data.get(
        "info",
        {}
    )

    outcome = info.get(
        "outcome",
        {}
    )

    # Test draws
    if outcome.get("result") == "draw":
        return "draw"

    # Ties
    if outcome.get("result") == "tie":
        return "tie"

    # No result
    if outcome.get("result") == "no result":
        return "no_result"

    winner = outcome.get(
        "winner"
    )

    innings = data.get(
        "innings",
        []
    )

    if not winner:
        return "unknown"

    if not innings:
        return "unknown"

    first_team = innings[0].get(
        "team"
    )

    if not first_team:
        return "unknown"

    if winner == first_team:

        return "batting_first"

    return "bowling_first"


def empty_group():

    return {
        "matches": 0,

        "city": "Unknown",

        "completed_matches": 0,

        "no_results": 0,

        "ties": 0,

        "draws": 0,

        "batting_first_matches": 0,

        "batting_first_wins": 0,

        "bowling_first_matches": 0,

        "bowling_first_wins": 0,

        "scores": [],

        "first_scores": [],

        "second_scores": [],

        "total_bowler_wickets": 0,

        "fast_wickets": 0,

        "medium_wickets": 0,

        "off_spin_wickets": 0,

        "leg_spin_wickets": 0,

        "unknown_wickets": 0
    }


def process_wickets(
    innings,
    group
):

    for wicket in get_wickets(
        innings
    ):

        kind = wicket.get(
            "kind"
        )

        if not is_bowler_wicket(
            kind
        ):
            continue

        group[
            "total_bowler_wickets"
        ] += 1

        bowler_type = classify_bowler(
            wicket.get(
                "bowler"
            )
        )

        if bowler_type == "fast":

            group[
                "fast_wickets"
            ] += 1

        elif bowler_type == "medium":

            group[
                "medium_wickets"
            ] += 1

        elif bowler_type == "off_spin":

            group[
                "off_spin_wickets"
            ] += 1

        elif bowler_type == "leg_spin":

            group[
                "leg_spin_wickets"
            ] += 1

        else:

            group[
                "unknown_wickets"
            ] += 1


def build_aggregates(
    data_directory
):

    aggregates = defaultdict(
        empty_group
    )

    processed = 0
    skipped = 0

    for file_path, data in load_json_files(
        data_directory
    ):

        metadata = get_match_metadata(
            data
        )

        venue = metadata[
            "venue"
        ]

        city = metadata[
            "city"
        ]

        match_format = metadata[
            "format"
        ]

        # ------------------------------------------
        # Only T20 / ODI / Test
        # ------------------------------------------

        if match_format not in {
            "T20",
            "ODI",
            "Test"
        }:

            skipped += 1
            continue

        if venue == "Unknown Venue":

            skipped += 1
            continue

        key = (
            venue,
            match_format
        )

        group = aggregates[
            key
        ]

        if group["city"] == "Unknown":
            group["city"] = city

        group[
            "matches"
        ] += 1

        processed += 1

        # ------------------------------------------
        # RESULT
        # ------------------------------------------

        result = determine_result(
            data
        )

        if result == "batting_first":

            group[
                "completed_matches"
            ] += 1

            group[
                "batting_first_matches"
            ] += 1

            group[
                "batting_first_wins"
            ] += 1

            group[
                "bowling_first_matches"
            ] += 1

        elif result == "bowling_first":

            group[
                "completed_matches"
            ] += 1

            group[
                "bowling_first_matches"
            ] += 1

            group[
                "bowling_first_wins"
            ] += 1

            group[
                "batting_first_matches"
            ] += 1

        elif result == "tie":

            group[
                "ties"
            ] += 1

        elif result == "draw":

            group[
                "draws"
            ] += 1

        elif result == "no_result":

            group[
                "no_results"
            ] += 1

        # ------------------------------------------
        # INNINGS
        # ------------------------------------------

        innings_list = data.get(
            "innings",
            []
        )

        for innings_number, innings in enumerate(
            innings_list,
            start=1
        ):

            score = calculate_innings_score(
                innings
            )

            group[
                "scores"
            ].append(score)

            if innings_number == 1:

                group[
                    "first_scores"
                ].append(score)

            elif innings_number == 2:

                group[
                    "second_scores"
                ].append(score)

            process_wickets(
                innings,
                group
            )

    print()
    print(
        "=========================================="
    )

    print(
        "CRICSHEET PROCESSING COMPLETE"
    )

    print(
        "=========================================="
    )

    print(
        f"Processed matches : {processed}"
    )

    print(
        f"Skipped matches   : {skipped}"
    )

    print(
        f"Venue-format groups: {len(aggregates)}"
    )

    print(
        "=========================================="
    )

    return aggregates


def percentage(
    numerator,
    denominator
):

    if denominator == 0:
        return 0.0

    return round(
        (
            numerator
            / denominator
        ) * 100,
        2
    )


def average(values):

    if not values:
        return 0.0

    return round(
        sum(values)
        / len(values),
        2
    )


def get_or_create_venue(
    venue_name,
    city
):

    venue = Venue.query.filter_by(
        name=venue_name
    ).order_by(Venue.id).first()

    if venue:
        return venue

    venue = Venue(
        name=venue_name,
        city=city,
        country="Unknown"
    )

    db.session.add(
        venue
    )

    db.session.flush()

    return venue


def save_statistics(
    aggregates
):

    saved = 0

    for (
        (venue_name, match_format),
        group
    ) in aggregates.items():

        venue = get_or_create_venue(
            venue_name,
            group["city"]
        )

        stats = VenueFormatStats.query.filter_by(
            venue_id=venue.id,
            format=match_format
        ).first()

        if not stats:

            stats = VenueFormatStats(
                venue_id=venue.id,
                format=match_format
            )

            db.session.add(
                stats
            )

        # ==========================================
        # MATCHES
        # ==========================================

        stats.matches = group[
            "matches"
        ]

        stats.completed_matches = group[
            "completed_matches"
        ]

        stats.no_results = group[
            "no_results"
        ]

        stats.ties = group[
            "ties"
        ]

        stats.draws = group[
            "draws"
        ]

        # ==========================================
        # BAT FIRST
        # ==========================================

        stats.batting_first_matches = group[
            "batting_first_matches"
        ]

        stats.batting_first_wins = group[
            "batting_first_wins"
        ]

        stats.batting_first_win_pct = percentage(
            group[
                "batting_first_wins"
            ],
            group[
                "batting_first_matches"
            ]
        )

        # ==========================================
        # BOWL FIRST
        # ==========================================

        stats.bowling_first_matches = group[
            "bowling_first_matches"
        ]

        stats.bowling_first_wins = group[
            "bowling_first_wins"
        ]

        stats.bowling_first_win_pct = percentage(
            group[
                "bowling_first_wins"
            ],
            group[
                "bowling_first_matches"
            ]
        )

        # ==========================================
        # ALL INNINGS
        # ==========================================

        scores = group[
            "scores"
        ]

        if scores:

            stats.innings_count = len(
                scores
            )

            stats.total_runs = sum(
                scores
            )

            stats.avg_score = average(
                scores
            )

            stats.max_score = max(
                scores
            )

            stats.min_score = min(
                scores
            )

        # ==========================================
        # FIRST INNINGS
        # ==========================================

        first_scores = group[
            "first_scores"
        ]

        if first_scores:

            stats.first_innings_count = len(
                first_scores
            )

            stats.first_innings_total_runs = sum(
                first_scores
            )

            stats.avg_first_innings_score = average(
                first_scores
            )

            stats.max_first_innings_score = max(
                first_scores
            )

            stats.min_first_innings_score = min(
                first_scores
            )

        # ==========================================
        # SECOND INNINGS
        # ==========================================

        second_scores = group[
            "second_scores"
        ]

        if second_scores:

            stats.second_innings_count = len(
                second_scores
            )

            stats.second_innings_total_runs = sum(
                second_scores
            )

            stats.avg_second_innings_score = average(
                second_scores
            )

            stats.max_second_innings_score = max(
                second_scores
            )

            stats.min_second_innings_score = min(
                second_scores
            )

        # ==========================================
        # WICKETS
        # ==========================================

        stats.total_bowler_wickets = group[
            "total_bowler_wickets"
        ]

        stats.fast_wickets = group[
            "fast_wickets"
        ]

        stats.medium_wickets = group[
            "medium_wickets"
        ]

        stats.off_spin_wickets = group[
            "off_spin_wickets"
        ]

        stats.leg_spin_wickets = group[
            "leg_spin_wickets"
        ]

        stats.unknown_wickets = group[
            "unknown_wickets"
        ]

        total_wickets = (
            stats.total_bowler_wickets
        )

        # ==========================================
        # WICKET PERCENTAGES
        # ==========================================

        stats.fast_wicket_pct = percentage(
            stats.fast_wickets,
            total_wickets
        )

        stats.medium_wicket_pct = percentage(
            stats.medium_wickets,
            total_wickets
        )

        stats.off_spin_wicket_pct = percentage(
            stats.off_spin_wickets,
            total_wickets
        )

        stats.leg_spin_wicket_pct = percentage(
            stats.leg_spin_wickets,
            total_wickets
        )

        pace_wickets = (
            stats.fast_wickets
            + stats.medium_wickets
        )

        spin_wickets = (
            stats.off_spin_wickets
            + stats.leg_spin_wickets
        )

        stats.pace_wicket_pct = percentage(
            pace_wickets,
            total_wickets
        )

        stats.spin_wicket_pct = percentage(
            spin_wickets,
            total_wickets
        )

        stats.data_source = "Cricsheet"

        saved += 1

    db.session.commit()

    return saved


def import_cricsheet_json(
    data_directory
):

    print()
    print(
        "=========================================="
    )

    print(
        "PITCHVISION AI"
    )

    print(
        "Historical Stadium Dataset Builder"
    )

    print(
        "=========================================="
    )

    print(
        f"Data directory: {data_directory}"
    )

    aggregates = build_aggregates(
        data_directory
    )

    saved = save_statistics(
        aggregates
    )

    print()
    print(
        "=========================================="
    )

    print(
        "DATABASE IMPORT COMPLETE"
    )

    print(
        f"Venue-format records: {saved}"
    )

    print(
        "=========================================="
    )

    return saved