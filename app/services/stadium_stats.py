from app.models import (
    Venue,
    VenueFormatStats
)


SUPPORTED_FORMATS = {
    "T20",
    "ODI",
    "Test"
}


def get_stadium_format_stats(
    venue_id,
    match_format
):

    if match_format not in SUPPORTED_FORMATS:

        return None

    stats = VenueFormatStats.query.filter_by(
        venue_id=venue_id,
        format=match_format
    ).first()

    if not stats:

        return None

    return stats.to_dict()


def get_stadium_all_formats(
    venue_id
):

    rows = VenueFormatStats.query.filter_by(
        venue_id=venue_id
    ).all()

    result = {}

    for row in rows:

        result[
            row.format
        ] = row.to_dict()

    return result


def get_stadium_summary(
    venue_id
):

    venue = Venue.query.get(
        venue_id
    )

    if not venue:

        return None

    return {
        "venue": venue.to_dict(),

        "formats": get_stadium_all_formats(
            venue_id
        )
    }


def get_format_comparison(
    venue_id
):

    result = {}

    for match_format in (
        "T20",
        "ODI",
        "Test"
    ):

        stats = get_stadium_format_stats(
            venue_id,
            match_format
        )

        if stats:

            result[
                match_format
            ] = stats

    return result