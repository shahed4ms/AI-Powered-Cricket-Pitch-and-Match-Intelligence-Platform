import json
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from flask import current_app
from app.services.ai_provider import create_ai_client, get_ai_settings


def generate_suggestions(match_data, weather_data, pitch_analysis, venue_stats, api_key=None):
    settings = get_ai_settings(api_key)
    if not settings:
        return {"error": "No AI provider key configured"}

    prompt = (
        "You are an expert cricket strategy advisor. Based on the following match context, "
        "provide detailed predictions and strategic suggestions.\n\n"
        f"Match: {match_data.get('match_name', 'N/A')}\n"
        f"Format: {match_data.get('format', 'N/A')}\n"
        f"Ball Type: {match_data.get('ball_type', 'Standard')}\n"
        f"Time: {match_data.get('time_start', 'N/A')} to {match_data.get('time_end', 'N/A')}\n\n"
        f"WEATHER DATA:\n{json.dumps(weather_data, indent=2) if weather_data else 'Not available'}\n\n"
        f"PITCH ANALYSIS:\n{json.dumps(pitch_analysis, indent=2) if pitch_analysis else 'No pitch image analyzed'}\n\n"
        f"VENUE HISTORIC STATS:\n{json.dumps(venue_stats, indent=2) if venue_stats else 'Not available'}\n\n"
        "Return ONLY valid JSON with this structure:\n"
        "{\n"
        '  "toss_suggestion": {"decision": "bat_first|bowl_first", "reasoning": "..."},\n'
        '  "score_prediction": {"first_innings": {"low": 250, "high": 300}, "second_innings": {"low": 230, "high": 280}, "confidence": 75},\n'
        '  "dew_factor": {"expected": true, "timing": "...", "impact": "..."},\n'
        '  "key_insights": ["insight1", "insight2", "insight3", "insight4", "insight5"],\n'
        '  "bowling_strategy": {"opening": "...", "middle": "...", "death": "..."},\n'
        '  "batting_strategy": {"approach": "...", "key_phases": "..."}\n'
        "}"
    )

    try:
        client = create_ai_client(settings)
        response = client.chat.completions.create(
            model=settings["model"],
            messages=[
                {"role": "system", "content": "You are a cricket strategy expert. Return only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=2500,
            response_format={"type": "json_object"},
        )
    except AuthenticationError:
        current_app.logger.warning("%s suggestions unavailable: authentication failed", settings["provider"])
        return {"error": f"{settings['provider'].title()} authentication failed. Check its API key."}
    except RateLimitError:
        current_app.logger.warning("%s suggestions unavailable: rate limit reached", settings["provider"])
        return {"error": f"{settings['provider'].title()} rate limit reached. Try again later."}
    except (APIConnectionError, APITimeoutError):
        current_app.logger.warning("%s suggestions unavailable: connection or timeout", settings["provider"])
        return {"error": "AI provider could not be reached. Local fallback analysis was used."}
    except APIStatusError as exc:
        current_app.logger.warning("%s suggestions unavailable: status=%s", settings["provider"], exc.status_code)
        return {"error": "AI provider returned an error. Local fallback analysis was used."}
    except Exception as exc:
        current_app.logger.warning("%s suggestions unavailable: %s", settings["provider"], exc.__class__.__name__)
        return {"error": "AI analysis failed. Local fallback analysis was used."}

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        suggestions = json.loads(raw)
        if not _is_valid_suggestions(suggestions):
            current_app.logger.warning("%s suggestions unavailable: response failed schema validation", settings["provider"])
            return {"error": "AI provider returned incomplete or invalid predictions. Local fallback analysis was used."}
        suggestions.setdefault("source", settings["provider"])
        return suggestions
    except json.JSONDecodeError:
        current_app.logger.warning("%s suggestions unavailable: response was not valid JSON", settings["provider"])
        return {"error": "AI provider returned an invalid response. Local fallback analysis was used."}


def generate_chat_response(match_data, analysis_data, question, history=None):
    settings = get_ai_settings()
    if not settings:
        return {"error": "No AI provider key configured"}

    context = (
        "You are PitchVisionAI, a practical cricket strategy assistant. Answer the user's question "
        "using only the supplied match context. Be specific, concise, and explain uncertainty. "
        "Never claim certainty about a toss, outcome, injury, or weather event.\n\n"
        f"MATCH CONTEXT:\n{json.dumps(match_data, indent=2)}\n\n"
        f"CURRENT ANALYSIS:\n{json.dumps(analysis_data, indent=2)}\n\n"
        "Give actionable cricket advice for the selected format and conditions."
    )
    messages = [{"role": "system", "content": context}]
    for item in (history or [])[-8:]:
        if isinstance(item, dict) and item.get("role") in {"user", "assistant"} and item.get("content"):
            messages.append({"role": item["role"], "content": str(item["content"])[:2000]})
    messages.append({"role": "user", "content": question})

    try:
        response = create_ai_client(settings).chat.completions.create(
            model=settings["model"],
            messages=messages,
            max_tokens=900,
        )
        answer = (response.choices[0].message.content or "").strip()
        if not answer:
            return {"error": "AI returned an empty response"}
        return {"reply": answer, "provider": settings["provider"]}
    except (AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as exc:
        current_app.logger.warning("%s chat unavailable: %s", settings["provider"], exc.__class__.__name__)
        return {"error": "AI chat is temporarily unavailable. Please try again."}
    except Exception as exc:
        current_app.logger.warning("%s chat failed: %s", settings["provider"], exc.__class__.__name__)
        return {"error": "AI chat could not answer that question."}


def _is_valid_suggestions(value):
    if not isinstance(value, dict):
        return False
    toss = value.get("toss_suggestion", {})
    score = value.get("score_prediction", {})
    first = score.get("first_innings", {})
    second = score.get("second_innings", {})
    decisions = {"bat_first", "bowl_first"}
    numeric = lambda item: isinstance(item, (int, float)) and not isinstance(item, bool)
    return (
        toss.get("decision") in decisions
        and isinstance(toss.get("reasoning"), str)
        and numeric(first.get("low")) and numeric(first.get("high"))
        and numeric(second.get("low")) and numeric(second.get("high"))
        and first["low"] <= first["high"]
        and second["low"] <= second["high"]
        and numeric(score.get("confidence"))
        and 0 <= score["confidence"] <= 100
        and isinstance(value.get("key_insights"), list)
    )


def build_fallback_suggestions(match_data, weather_data, pitch_analysis, venue_stats, reason=None):
    """Build useful local suggestions when the optional AI provider is unavailable."""
    venue_stats = venue_stats or {}
    weather_data = weather_data or {}
    pitch_analysis = pitch_analysis or {}

    format_baselines = {"Test": 300, "ODI": 265, "T20": 175, "Custom": 240}
    format_name = match_data.get("format") or "Custom"
    format_baseline = format_baselines.get(format_name, format_baselines["Custom"])
    average_score = venue_stats.get("avg_score")
    try:
        average_score = int(round(float(average_score))) if average_score is not None else 240
    except (TypeError, ValueError):
        average_score = format_baseline
    else:
        average_score = round((average_score * 0.65) + (format_baseline * 0.35))

    first_win_pct = float(venue_stats.get("batting_first_win_pct") or 50)
    second_win_pct = float(venue_stats.get("batting_second_win_pct") or 50)
    decision = "bat_first" if first_win_pct >= second_win_pct else "bowl_first"
    decision_reason = (
        f"Historical venue results favor batting first ({first_win_pct:.0f}% wins)."
        if decision == "bat_first"
        else f"Historical venue results favor chasing ({second_win_pct:.0f}% wins batting second)."
    )

    current_weather = weather_data.get("current") or {}
    hourly_weather = weather_data.get("hourly") or []
    humidity = current_weather.get("humidity")
    try:
        humidity = float(humidity) if humidity is not None else 0
    except (TypeError, ValueError):
        humidity = 0
    start_time = str(match_data.get("time_start") or "")
    try:
        start_hour = int(start_time.split(":", 1)[0])
    except (TypeError, ValueError):
        start_hour = 0
    rain_probability = max((float(item.get("rain_probability") or 0) for item in hourly_weather), default=0)
    dew_expected = humidity >= 70 and start_hour >= 16
    weather_adjustment = -15 if rain_probability >= 60 else -8 if rain_probability >= 35 else 0
    average_score = max(80, average_score + weather_adjustment)

    pitch_type = pitch_analysis.get("pitch_type") or venue_stats.get("pitch_type") or "unknown"
    pitch_note = f"The venue profile suggests a {pitch_type} pitch; adjust batting tempo to the early movement."
    weather_note = (
        "High humidity may make the ball harder to grip later, so keep a reliable death-overs option ready."
        if dew_expected
        else "Monitor the forecast at the toss and reassess if conditions change."
    )

    return {
        "source": "fallback",
        "fallback_reason": reason or "Optional AI provider was unavailable.",
        "toss_suggestion": {"decision": decision, "reasoning": decision_reason},
        "score_prediction": {
            "first_innings": {"low": max(100, average_score - 20), "high": average_score + 20},
            "second_innings": {"low": max(80, average_score - 30), "high": average_score + 10},
            "confidence": 48 if not venue_stats else 58,
        },
        "dew_factor": {
            "expected": dew_expected,
            "timing": "After sunset" if dew_expected else "Not strongly indicated",
            "impact": weather_note,
        },
        "key_insights": [
            pitch_note,
            weather_note,
            f"Use {average_score} as the venue's baseline first-innings score.",
            "Reassess the plan after the toss with the latest surface and weather observations.",
        ],
        "bowling_strategy": {
            "opening": "Use your best movement bowlers early and attack the outside edge.",
            "middle": "Protect the highest-scoring areas and rotate spin or change-ups through the middle overs.",
            "death": "Keep two yorker or slower-ball options for the final overs.",
        },
        "batting_strategy": {
            "approach": "Build a stable platform before increasing the scoring rate.",
            "key_phases": "Preserve wickets in the powerplay, target matchups in the middle overs, and finish with depth.",
        },
    }
