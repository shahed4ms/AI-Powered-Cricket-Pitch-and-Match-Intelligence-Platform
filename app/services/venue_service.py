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
    q = (query or "").strip()
    if not q:
        return []

    q_lower = q.lower()

    def score_venue(venue):
        name = (venue.name or "").lower()
        city = (venue.city or "").lower()
        is_city_entry = name == city
        is_cricket_ground = any(term in name for term in ("stadium", "ground", "oval", "cricket"))

        if is_cricket_ground and city == q_lower:
            return (-1, 0, name)
        if city == q_lower and not is_city_entry:
            return (0, 0, name)
        if name == q_lower and not is_city_entry:
            return (1, 0, name)
        if name.startswith(q_lower) and not is_city_entry:
            return (2, 0, name)
        if city.startswith(q_lower) and not is_city_entry:
            return (3, 0, name)
        if q_lower in city and not is_city_entry:
            return (4, 0, name)
        if q_lower in name and not is_city_entry:
            return (5, 0, name)
        if city == q_lower and is_city_entry:
            return (6, 0, name)
        if name == q_lower and is_city_entry:
            return (7, 0, name)
        return (8, 0, name)

    db_results = Venue.query.filter(
        db.or_(
            Venue.name.ilike(f"%{q}%"),
            Venue.city.ilike(f"%{q}%"),
            Venue.country.ilike(f"%{q}%"),
        )
    ).all()
    db_results = sorted(db_results, key=score_venue)[:10]

    if len(db_results) < 3 and api_key:
        api_results = search_cricketdata_api(q, api_key)
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
        for item in search_city_geocoding(q):
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

    def add_label(item, kind):
        name = (item.get("name") or "").strip()
        city = (item.get("city") or "").strip()
        country = (item.get("country") or "").strip()
        label_parts = [part for part in [name, city, country] if part]
        item["label"] = ", ".join(label_parts)
        item["kind"] = kind
        return item

    def venue_sort_key(item):
        name = (item.get("name") or "").lower()
        city = (item.get("city") or "").lower()
        is_city_entry = name == city
        is_cricket_ground = any(term in name for term in ("stadium", "ground", "oval", "cricket"))

        if is_cricket_ground and city == q_lower:
            priority = -1
        elif city == q_lower and not is_city_entry:
            priority = 0
        elif name == q_lower and not is_city_entry:
            priority = 1
        elif name.startswith(q_lower) and not is_city_entry:
            priority = 2
        elif city.startswith(q_lower) and not is_city_entry:
            priority = 3
        elif q_lower in city and not is_city_entry:
            priority = 4
        elif q_lower in name and not is_city_entry:
            priority = 5
        elif city == q_lower and is_city_entry:
            priority = 6
        elif name == q_lower and is_city_entry:
            priority = 7
        else:
            priority = 8

        return (priority, name)

    results = [add_label({**venue.to_dict(), "kind": "Stadium"}, "Stadium") for venue in db_results[:8]]
    results = sorted(results, key=venue_sort_key)
    city_results = sorted(city_results, key=lambda venue: ((0 if (venue.city or "").lower() == q_lower else 1), (venue.city or "").lower()))
    results.extend(add_label({**venue.to_dict(), "kind": "City"}, "City") for venue in city_results[:2])
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

    The payload includes both the selected format summary and a full
    comparison across T20, ODI, and Test matches so the UI can display
    accurate score ranges for all supported formats.
    """

    venue = Venue.query.get(
        venue_id
    )

    if not venue:
        return None

    result = venue.to_dict()
    supported_formats = ("T20", "ODI", "Test")
    comparison = {}

    for fmt in supported_formats:
        stats = get_stadium_format_stats(venue_id, fmt)
        if stats:
            comparison[fmt] = stats

    selected_stats = None
    if match_format and match_format in supported_formats:
        selected_stats = comparison.get(match_format) or get_stadium_format_stats(venue_id, match_format)
        if selected_stats:
            result["selected_format"] = match_format
            result["historical"] = selected_stats
        elif comparison:
            result["selected_format"] = next(iter(comparison.keys()), "T20")
            result["historical"] = comparison[result["selected_format"]]
        else:
            result["selected_format"] = match_format
            result["historical"] = None
    elif comparison:
        result["selected_format"] = next(iter(comparison.keys()), "T20")
        result["historical"] = comparison[result["selected_format"]]
    else:
        result["selected_format"] = match_format
        result["historical"] = get_stadium_format_stats(venue_id, match_format) if match_format else None

    result["format_comparison"] = comparison

    return result
