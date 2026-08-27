import json
import csv
from pathlib import Path
from collections import defaultdict


# ============================================================
# PATHS
# ============================================================

PROJECT_ROOT = Path(__file__).resolve().parent.parent

JSON_FOLDER = PROJECT_ROOT / "all_json"

OUTPUT_FOLDER = PROJECT_ROOT / "historical_data" / "output"
OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

OUTPUT_CSV = OUTPUT_FOLDER / "stadium_format_stats.csv"
OUTPUT_JSON = OUTPUT_FOLDER / "stadium_format_stats.json"
REPORT_JSON = OUTPUT_FOLDER / "processing_report.json"


# ============================================================
# ONLY THESE FORMATS
# ============================================================

VALID_FORMATS = {
    "T20",
    "ODI",
    "Test",
}


# ============================================================
# BOWLER CLASSIFICATION
# ============================================================

def classify_bowler_style(style):
    """
    Converts a bowling-style description into one of:

        fast
        medium
        off_spin
        leg_spin
        unknown
    """

    if not style:
        return "unknown"

    value = str(style).lower().strip()

    # Off spin
    if any(x in value for x in [
        "offbreak",
        "off break",
        "off-spin",
        "off spin",
        "orthodox",
    ]):
        return "off_spin"

    # Leg spin
    if any(x in value for x in [
        "legbreak",
        "leg break",
        "leg-spin",
        "leg spin",
        "googly",
        "wrist spin",
        "wrist-spin",
    ]):
        return "leg_spin"

    # Medium
    if any(x in value for x in [
        "medium",
        "medium-fast",
        "medium fast",
        "medium-pace",
        "medium pace",
    ]):
        return "medium"

    # Fast
    if any(x in value for x in [
        "fast",
        "pace",
    ]):
        return "fast"

    return "unknown"


# ============================================================
# EMPTY RECORD
# ============================================================

def empty_record(venue, match_format):

    return {
        "venue": venue,
        "format": match_format,

        "matches": 0,
        "completed_matches": 0,
        "no_results": 0,
        "ties": 0,
        "draws": 0,

        "batting_first_matches": 0,
        "batting_first_wins": 0,
        "batting_first_win_pct": 0.0,

        "bowling_first_matches": 0,
        "bowling_first_wins": 0,
        "bowling_first_win_pct": 0.0,

        "innings_count": 0,
        "total_runs": 0,

        "first_innings_count": 0,
        "first_innings_total_runs": 0,

        "second_innings_count": 0,
        "second_innings_total_runs": 0,

        "scores": [],
        "first_scores": [],
        "second_scores": [],

        "total_bowler_wickets": 0,

        "fast_wickets": 0,
        "medium_wickets": 0,
        "off_spin_wickets": 0,
        "leg_spin_wickets": 0,
        "unknown_wickets": 0,
    }


# ============================================================
# GET FORMAT
# ============================================================

def get_format(data):

    match_type = data.get("info", {}).get("match_type")

    if not match_type:
        return None

    match_type = str(match_type).strip()

    if match_type in VALID_FORMATS:
        return match_type

    return None


# ============================================================
# GET VENUE
# ============================================================

def get_venue(data):

    venue = data.get("info", {}).get("venue")

    if not venue:
        return "Unknown Venue"

    return str(venue).strip()


# ============================================================
# GET OUTCOME
# ============================================================

def get_outcome(data):

    outcome = data.get("info", {}).get("outcome", {})

    if not isinstance(outcome, dict):
        return {}

    return outcome


# ============================================================
# GET TOSS
# ============================================================

def get_toss(data):

    toss = data.get("info", {}).get("toss", {})

    if not isinstance(toss, dict):
        return None, None

    return (
        toss.get("winner"),
        toss.get("decision"),
    )


# ============================================================
# GET INNINGS TEAM
# ============================================================

def get_innings_team(innings):

    return innings.get("team")


# ============================================================
# DELIVERY ITERATOR
# ============================================================

def deliveries_from_innings(innings):

    for over in innings.get("overs", []):

        for delivery in over.get("deliveries", []):

            yield delivery


# ============================================================
# CALCULATE INNINGS SCORE
# ============================================================

def calculate_innings_score(innings):

    total = 0

    for delivery in deliveries_from_innings(innings):

        runs = delivery.get("runs", {})

        if isinstance(runs, dict):

            total += int(
                runs.get("total", 0) or 0
            )

    return total


# ============================================================
# DETERMINE BAT FIRST
# ============================================================

def determine_batting_first(
    data,
    innings
):

    if not innings:
        return None

    # The first innings team is the team batting first.
    return innings[0].get("team")


# ============================================================
# DETERMINE RESULT TYPE
# ============================================================

def determine_result_type(outcome):

    if not outcome:
        return "unknown"

    if outcome.get("winner"):
        return "winner"

    result = str(
        outcome.get("result", "")
    ).lower().strip()

    if result == "tie":
        return "tie"

    if result == "draw":
        return "draw"

    if result in [
        "no result",
        "no_result",
        "abandoned",
    ]:
        return "no_result"

    return "unknown"


# ============================================================
# PROCESS WIN RESULT
# ============================================================

def process_match_result(
    record,
    data,
    innings
):

    outcome = get_outcome(data)

    result_type = determine_result_type(
        outcome
    )

    winner = outcome.get("winner")

    # --------------------------------------------
    # Draw
    # --------------------------------------------

    if result_type == "draw":

        record["draws"] += 1

        return

    # --------------------------------------------
    # Tie
    # --------------------------------------------

    if result_type == "tie":

        record["ties"] += 1

        return

    # --------------------------------------------
    # No result
    # --------------------------------------------

    if result_type == "no_result":

        record["no_results"] += 1

        return

    # --------------------------------------------
    # No winner
    # --------------------------------------------

    if not winner:

        return

    record["completed_matches"] += 1

    # --------------------------------------------
    # Need innings order
    # --------------------------------------------

    if not innings:

        return

    batting_first_team = (
        innings[0].get("team")
    )

    if not batting_first_team:

        return

    # --------------------------------------------
    # Winner batted first
    # --------------------------------------------

    if winner == batting_first_team:

        record[
            "batting_first_matches"
        ] += 1

        record[
            "batting_first_wins"
        ] += 1

    # --------------------------------------------
    # Winner chased
    # --------------------------------------------

    else:

        record[
            "bowling_first_matches"
        ] += 1

        record[
            "bowling_first_wins"
        ] += 1


# ============================================================
# WICKET PROCESSING
# ============================================================

def process_wickets(
    record,
    data,
    delivery
):

    wickets = delivery.get(
        "wickets",
        []
    )

    if not isinstance(wickets, list):
        return

    for wicket in wickets:

        if not isinstance(wicket, dict):
            continue

        kind = str(
            wicket.get("kind", "")
        ).lower().strip()

        # These are not credited to bowler
        non_bowler_wickets = {
            "retired hurt",
            "retired out",
            "obstructing the field",
        }

        if kind in non_bowler_wickets:
            continue

        record[
            "total_bowler_wickets"
        ] += 1

        # ----------------------------------------------------
        # IMPORTANT
        # ----------------------------------------------------
        #
        # Cricsheet match JSON does not contain a reliable
        # bowling-style field in info.players.
        #
        # Therefore, until we provide a bowler-style mapping,
        # these wickets remain unknown.
        #

        record[
            "unknown_wickets"
        ] += 1


# ============================================================
# PROCESS INNINGS
# ============================================================

def process_innings(
    record,
    innings_index,
    innings,
    data
):

    score = 0

    for delivery in deliveries_from_innings(
        innings
    ):

        runs = delivery.get(
            "runs",
            {}
        )

        if isinstance(runs, dict):

            score += int(
                runs.get(
                    "total",
                    0
                ) or 0
            )

        process_wickets(
            record,
            data,
            delivery
        )

    record[
        "innings_count"
    ] += 1

    record[
        "total_runs"
    ] += score

    record[
        "scores"
    ].append(score)

    # First innings
    if innings_index == 0:

        record[
            "first_innings_count"
        ] += 1

        record[
            "first_innings_total_runs"
        ] += score

        record[
            "first_scores"
        ].append(score)

    # Second innings
    elif innings_index == 1:

        record[
            "second_innings_count"
        ] += 1

        record[
            "second_innings_total_runs"
        ] += score

        record[
            "second_scores"
        ].append(score)


# ============================================================
# PROCESS ONE MATCH
# ============================================================

def process_match(
    data,
    statistics
):

    match_format = get_format(data)

    if not match_format:

        return False, "unsupported_format"

    venue = get_venue(data)

    key = (
        venue,
        match_format
    )

    if key not in statistics:

        statistics[key] = empty_record(
            venue,
            match_format
        )

    record = statistics[key]

    record["matches"] += 1

    innings = data.get(
        "innings",
        []
    )

    if not isinstance(innings, list):
        innings = []

    # Result
    process_match_result(
        record,
        data,
        innings
    )

    # Innings
    for index, current_innings in enumerate(
        innings
    ):

        if not isinstance(
            current_innings,
            dict
        ):
            continue

        process_innings(
            record,
            index,
            current_innings,
            data
        )

    return True, "processed"


# ============================================================
# PERCENTAGE
# ============================================================

def pct(part, total):

    if total == 0:
        return 0.0

    return round(
        part * 100.0 / total,
        2
    )


# ============================================================
# FINALIZE RECORD
# ============================================================

def finalize_record(record):

    scores = record["scores"]
    first_scores = record["first_scores"]
    second_scores = record["second_scores"]

    # --------------------------------------------
    # Average / max / min
    # --------------------------------------------

    record["avg_score"] = (
        round(
            sum(scores) / len(scores),
            2
        )
        if scores
        else 0.0
    )

    record["max_score"] = (
        max(scores)
        if scores
        else 0
    )

    record["min_score"] = (
        min(scores)
        if scores
        else 0
    )

    # --------------------------------------------
    # First innings
    # --------------------------------------------

    record[
        "avg_first_innings_score"
    ] = (
        round(
            sum(first_scores)
            / len(first_scores),
            2
        )
        if first_scores
        else 0.0
    )

    record[
        "max_first_innings_score"
    ] = (
        max(first_scores)
        if first_scores
        else 0
    )

    record[
        "min_first_innings_score"
    ] = (
        min(first_scores)
        if first_scores
        else 0
    )

    # --------------------------------------------
    # Second innings
    # --------------------------------------------

    record[
        "avg_second_innings_score"
    ] = (
        round(
            sum(second_scores)
            / len(second_scores),
            2
        )
        if second_scores
        else 0.0
    )

    record[
        "max_second_innings_score"
    ] = (
        max(second_scores)
        if second_scores
        else 0
    )

    record[
        "min_second_innings_score"
    ] = (
        min(second_scores)
        if second_scores
        else 0
    )

    # --------------------------------------------
    # Winning percentages
    # --------------------------------------------

    record[
        "batting_first_win_pct"
    ] = pct(
        record["batting_first_wins"],
        record["batting_first_matches"]
    )

    record[
        "bowling_first_win_pct"
    ] = pct(
        record["bowling_first_wins"],
        record["bowling_first_matches"]
    )

    # --------------------------------------------
    # Wicket percentages
    # --------------------------------------------

    total_wickets = record[
        "total_bowler_wickets"
    ]

    record[
        "fast_wicket_pct"
    ] = pct(
        record["fast_wickets"],
        total_wickets
    )

    record[
        "medium_wicket_pct"
    ] = pct(
        record["medium_wickets"],
        total_wickets
    )

    record[
        "off_spin_wicket_pct"
    ] = pct(
        record["off_spin_wickets"],
        total_wickets
    )

    record[
        "leg_spin_wicket_pct"
    ] = pct(
        record["leg_spin_wickets"],
        total_wickets
    )

    pace_wickets = (
        record["fast_wickets"]
        + record["medium_wickets"]
    )

    spin_wickets = (
        record["off_spin_wickets"]
        + record["leg_spin_wickets"]
    )

    record[
        "pace_wicket_pct"
    ] = pct(
        pace_wickets,
        total_wickets
    )

    record[
        "spin_wicket_pct"
    ] = pct(
        spin_wickets,
        total_wickets
    )

    # Remove internal arrays

    record.pop("scores", None)
    record.pop("first_scores", None)
    record.pop("second_scores", None)

    return record


# ============================================================
# MAIN
# ============================================================

def main():

    print("=" * 70)
    print(
        "PITCHVISION AI - STADIUM HISTORICAL DATA"
    )
    print("=" * 70)

    if not JSON_FOLDER.exists():

        print(
            f"ERROR: {JSON_FOLDER} does not exist"
        )

        return

    json_files = list(
        JSON_FOLDER.rglob("*.json")
    )

    print(
        f"\nJSON files found: {len(json_files)}"
    )

    statistics = {}

    processed = 0
    skipped = 0
    failed = 0

    skipped_formats = defaultdict(int)
    errors = []

    # --------------------------------------------
    # PROCESS FILES
    # --------------------------------------------

    for index, json_file in enumerate(
        json_files,
        start=1
    ):

        try:

            with open(
                json_file,
                "r",
                encoding="utf-8"
            ) as f:

                data = json.load(f)

            match_format = get_format(
                data
            )

            if not match_format:

                skipped += 1

                raw_format = (
                    data
                    .get("info", {})
                    .get("match_type", "UNKNOWN")
                )

                skipped_formats[
                    str(raw_format)
                ] += 1

                continue

            success, reason = process_match(
                data,
                statistics
            )

            if success:

                processed += 1

            else:

                skipped += 1

        except Exception as exc:

            failed += 1

            if len(errors) < 20:

                errors.append({
                    "file": str(json_file),
                    "error": str(exc),
                })

        if index % 500 == 0:

            print(
                f"Processed {index}/{len(json_files)}..."
            )

    # --------------------------------------------
    # FINALIZE
    # --------------------------------------------

    records = []

    for record in statistics.values():

        records.append(
            finalize_record(record)
        )

    records.sort(
        key=lambda x: (
            x["venue"].lower(),
            x["format"]
        )
    )

    # --------------------------------------------
    # CSV
    # --------------------------------------------

    if records:

        fieldnames = list(
            records[0].keys()
        )

        with open(
            OUTPUT_CSV,
            "w",
            newline="",
            encoding="utf-8"
        ) as f:

            writer = csv.DictWriter(
                f,
                fieldnames=fieldnames
            )

            writer.writeheader()

            writer.writerows(records)

    # --------------------------------------------
    # JSON
    # --------------------------------------------

    with open(
        OUTPUT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            records,
            f,
            indent=2,
            ensure_ascii=False
        )

    # --------------------------------------------
    # REPORT
    # --------------------------------------------

    report = {

        "source_folder": str(
            JSON_FOLDER
        ),

        "total_json_files": len(
            json_files
        ),

        "processed_files": processed,

        "skipped_files": skipped,

        "failed_files": failed,

        "stadium_format_groups": len(
            records
        ),

        "venues_found": len(
            {
                r["venue"]
                for r in records
            }
        ),

        "formats_found": sorted(
            {
                r["format"]
                for r in records
            }
        ),

        "skipped_formats": dict(
            sorted(
                skipped_formats.items()
            )
        ),

        "error_examples": errors,

        "bowler_style_note":
            "Bowling style is not directly available "
            "in the match JSON structure inspected. "
            "Wickets are therefore currently classified "
            "as unknown until a bowler-style mapping is added."
    }

    with open(
        REPORT_JSON,
        "w",
        encoding="utf-8"
    ) as f:

        json.dump(
            report,
            f,
            indent=2
        )

    # --------------------------------------------
    # SUMMARY
    # --------------------------------------------

    print("\n" + "=" * 70)
    print("PROCESSING COMPLETE")
    print("=" * 70)

    print(
        f"Total files      : {len(json_files)}"
    )

    print(
        f"Processed        : {processed}"
    )

    print(
        f"Skipped          : {skipped}"
    )

    print(
        f"Failed           : {failed}"
    )

    print(
        f"Venues           : {report['venues_found']}"
    )

    print(
        f"Venue+format     : {report['stadium_format_groups']}"
    )

    print(
        f"Formats          : {report['formats_found']}"
    )

    print("\nOutputs:")

    print(
        f"CSV    : {OUTPUT_CSV}"
    )

    print(
        f"JSON   : {OUTPUT_JSON}"
    )

    print(
        f"Report : {REPORT_JSON}"
    )

    print("=" * 70)


if __name__ == "__main__":
    main()