import requests
from app.models import Venue
from app.extensions import db


CRICKETDATA_BASE = "https://api.cricdata.org/v1"
GEOCODING_URL = "https://geocoding-api.open-meteo.com/v1/search"


def search_cricketdata_api(query, api_key):
    if not api_key:
        return []
    try:
        resp = requests.get(
            f"{CRICKETDATA_BASE}/venues",
            params={"search": query},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        return resp.json().get("data", [])
    except Exception:
        return []


def search_city_geocoding(query):
    try:
        response = requests.get(
            GEOCODING_URL,
            params={"name": query, "count": 3, "language": "en", "format": "json"},
            timeout=5,
        )
        response.raise_for_status()
        return response.json().get("results", [])
    except (requests.RequestException, ValueError):
        return []


def search_venues(query, api_key=None):
    db_results = Venue.query.filter(
        db.or_(
            Venue.name.ilike(f"%{query}%"),
            Venue.city.ilike(f"%{query}%"),
            Venue.country.ilike(f"%{query}%"),
        )
    ).order_by(Venue.name).limit(10).all()

    if len(db_results) < 3 and api_key:
        api_results = search_cricketdata_api(query, api_key)
        for item in api_results:
            existing = Venue.query.filter_by(name=item.get("name", "")).first()
            if not existing:
                venue = Venue(
                    name=item.get("name", "Unknown"),
                    city=item.get("city", "Unknown"),
                    country=item.get("country", "Unknown"),
                    latitude=item.get("latitude"),
                    longitude=item.get("longitude"),
                )
                db.session.add(venue)
                db_results.append(venue)

    city_results = []
    if len(db_results) < 10:
        for item in search_city_geocoding(query):
            city_name = item.get("name")
            if not city_name or item.get("latitude") is None or item.get("longitude") is None:
                continue
            city = item.get("admin1") or city_name
            existing = Venue.query.filter_by(name=city_name, city=city).first()
            if not existing:
                existing = Venue(
                    name=city_name,
                    city=city,
                    country=item.get("country", "Unknown"),
                    latitude=item["latitude"],
                    longitude=item["longitude"],
                )
                db.session.add(existing)
            city_results.append(existing)

    db.session.commit()
    results = [{**venue.to_dict(), "kind": "Stadium"} for venue in db_results[:8]]
    results.extend({**venue.to_dict(), "kind": "City"} for venue in city_results[:2])
    return results


from app.models import Venue
from app.services.stadium_stats import (
    get_stadium_format_stats,
    get_stadium_all_formats,
)


def get_venue_stats(
    venue_id,
    match_format=None
):
    """
    Return historical stadium statistics.

    If format is supplied:
        return only that format.

    Otherwise:
        return all formats.
    """

    venue = Venue.query.get(
        venue_id
    )

    if not venue:
        return None

    result = venue.to_dict()

    if match_format:

        stats = get_stadium_format_stats(
            venue_id,
            match_format
        )

        result["historical"] = stats

    else:

        result["historical"] = get_stadium_all_formats(
            venue_id
        )

    return result
