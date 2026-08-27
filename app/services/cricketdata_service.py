import requests


CRICKETDATA_BASE = "https://api.cricdata.org/v1"


def get_venue_stats_from_api(venue_name, api_key):
    if not api_key:
        return None
    try:
        resp = requests.get(
            f"{CRICKETDATA_BASE}/venues",
            params={"search": venue_name},
            headers={"Authorization": f"Bearer {api_key}"},
            timeout=10,
        )
        resp.raise_for_status()
        data = resp.json().get("data", [])
        if data:
            return data[0]
        return None
    except Exception:
        return None
