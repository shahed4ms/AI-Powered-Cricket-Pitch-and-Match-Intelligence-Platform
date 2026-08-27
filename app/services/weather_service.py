import requests
from datetime import datetime, time, timedelta
from flask import current_app


OPEN_METEO_URL = "https://api.open-meteo.com/v1/forecast"


def get_weather_forecast(latitude, longitude, date_obj, time_start=None, time_end=None, date_end=None, continuous=False):
    start_date = date_obj.date() if isinstance(date_obj, datetime) else date_obj
    finish_date = date_end or start_date
    params = {
        "latitude": latitude,
        "longitude": longitude,
        "hourly": "temperature_2m,relative_humidity_2m,wind_speed_10m,wind_direction_10m,precipitation_probability,weather_code",
        "timezone": "auto",
        "start_date": start_date.isoformat(),
        "end_date": finish_date.isoformat(),
    }

    try:
        resp = requests.get(OPEN_METEO_URL, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()
    except requests.RequestException as exc:
        current_app.logger.warning("Weather provider unavailable: %s", exc.__class__.__name__)
        return {"error": "Weather provider unavailable", "provider": "open_meteo"}
    except (TypeError, ValueError, KeyError) as exc:
        current_app.logger.warning("Weather response could not be parsed: %s", exc.__class__.__name__)
        return {"error": "Weather response could not be parsed", "provider": "open_meteo"}

    hourly = data.get("hourly", {})
    times = hourly.get("time", [])
    result = []

    start_clock = _as_time(time_start)
    end_clock = _as_time(time_end)
    continuous_start = datetime.combine(start_date, start_clock) if continuous and start_clock else None
    continuous_end = continuous_start + timedelta(hours=6) if continuous_start else None
    for i, timestamp in enumerate(times):
        forecast_time = datetime.fromisoformat(timestamp)
        if continuous_start and not continuous_start <= forecast_time <= continuous_end:
            continue
        if not continuous_start and not _in_match_window(forecast_time.time(), start_clock, end_clock):
            continue

        result.append({
            "time": timestamp,
            "hour": forecast_time.hour,
            "temperature": hourly.get("temperature_2m", [None])[i],
            "humidity": hourly.get("relative_humidity_2m", [None])[i],
            "wind_speed": hourly.get("wind_speed_10m", [None])[i],
            "wind_direction": hourly.get("wind_direction_10m", [None])[i],
            "rain_probability": hourly.get("precipitation_probability", [None])[i],
            "weather_code": hourly.get("weather_code", [None])[i],
        })

    current = None
    if result:
        utc_offset = data.get("utc_offset_seconds") or 0
        now = datetime.utcnow() + timedelta(seconds=utc_offset)
        future_points = [point for point in result if datetime.fromisoformat(point["time"]) >= now]
        current = min(future_points or result, key=lambda point: abs(
            datetime.fromisoformat(point["time"]) - now
        ))

    return {
        "current": current,
        "hourly": result,
        "timezone": data.get("timezone"),
        "timezone_abbreviation": data.get("timezone_abbreviation"),
        "utc_offset_seconds": data.get("utc_offset_seconds"),
        "provider": "open_meteo",
        "date_start": start_date.isoformat(),
        "date_end": finish_date.isoformat(),
    }


def _as_time(value):
    if value is None:
        return None
    if isinstance(value, time):
        return value
    return time.fromisoformat(str(value))


def _in_match_window(forecast_time, start_clock, end_clock):
    if not start_clock and not end_clock:
        return True
    if start_clock and not end_clock:
        return forecast_time >= start_clock
    if end_clock and not start_clock:
        return forecast_time <= end_clock
    if start_clock <= end_clock:
        return start_clock <= forecast_time <= end_clock
    return forecast_time >= start_clock or forecast_time <= end_clock


def enrich_weather_data(data):
    if not data or data.get("error"):
        return data

    current = data.get("current")
    if current:
        current["description"] = get_weather_description(current.get("weather_code"))
        current["compass"] = degrees_to_compass(current.get("wind_direction"))
    for hourly in data.get("hourly", []):
        hourly["description"] = get_weather_description(hourly.get("weather_code"))
        hourly["compass"] = degrees_to_compass(hourly.get("wind_direction"))
    return data


def get_weather_description(code):
    codes = {
        0: "Clear sky", 1: "Mainly clear", 2: "Partly cloudy", 3: "Overcast",
        45: "Foggy", 48: "Rime fog", 51: "Light drizzle", 53: "Moderate drizzle",
        55: "Dense drizzle", 61: "Slight rain", 63: "Moderate rain", 65: "Heavy rain",
        71: "Slight snow", 73: "Moderate snow", 75: "Heavy snow", 80: "Slight showers",
        81: "Moderate showers", 82: "Violent showers", 95: "Thunderstorm",
        96: "Thunderstorm with hail", 99: "Thunderstorm with heavy hail",
    }
    return codes.get(code, "Unknown")


def degrees_to_compass(deg):
    if deg is None:
        return "N/A"
    directions = ["N", "NNE", "NE", "ENE", "E", "ESE", "SE", "SSE",
                  "S", "SSW", "SW", "WSW", "W", "WNW", "NW", "NNW"]
    idx = round(deg / 22.5) % 16
    return directions[idx]
