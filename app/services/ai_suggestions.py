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


def _fallback_chat_reply(match_data, analysis_data, question):
    venue = (match_data or {}).get("venue") or {}
    venue_name = venue.get("name") or "the venue"
    format_name = (match_data or {}).get("format") or "the match"
    weather = (analysis_data or {}).get("weather") or {}
    pitch = (analysis_data or {}).get("pitch") or {}
    venue_stats = (analysis_data or {}).get("venue_stats") or {}
    score_prediction = ((analysis_data or {}).get("predictions") or {}).get("score_prediction") or {}

    first_pred = score_prediction.get("first_innings") or {}
    second_pred = score_prediction.get("second_innings") or {}
    weather_text = "Weather is not strongly indicating a major swing, so focus on the toss and team plan."
    if weather:
        hourly = (weather.get("hourly") or [])
        if hourly:
            rain_prob = max(float(item.get("rain_probability") or 0) for item in hourly)
            if rain_prob >= 40:
                weather_text = "Rain risk is meaningful, so keep the plan flexible and prepare for a shorter, more adaptive innings."
            else:
                weather_text = "Conditions look stable, which supports a measured approach rather than a chaotic chase."

    if pitch:
        pitch_type = pitch.get("pitch_type") or pitch.get("surface") or "balanced"
        weather_text += f" The pitch profile suggests a {pitch_type} surface, so match-ups and early rotation matter."

    avg_score = venue_stats.get("avg_score") or ((venue_stats.get("scores") or {}).get("all_innings") or {}).get("average")
    score_hint = f"Your venue baseline is around {int(round(float(avg_score))) if avg_score is not None else 'a moderate'} runs." if avg_score is not None else "Use the local venue baseline as your anchor rather than chasing a number too early."

    first_range = first_pred.get("low") and first_pred.get("high")
    second_range = second_pred.get("low") and second_pred.get("high")
    range_text = ""
    if first_range and second_range:
        range_text = f" For the current match profile, a first-innings range of {first_pred['low']}-{first_pred['high']} and a second-innings range of {second_pred['low']}-{second_pred['high']} is a reasonable planning window."

    return (
        f"Local strategy view for {format_name} at {venue_name}: {score_hint}{range_text} "
        f"{weather_text} Keep the first 6-8 overs disciplined, prioritize wicket preservation, and then accelerate only when the matchup is clear. "
        f"If your question is about the toss, target the conditions and the venue trend rather than one fixed rule; if it is about batting, build a stable platform before pushing the scoring rate."
    )


def generate_chat_response(match_data, analysis_data, question, history=None):
    settings = get_ai_settings()
    if not settings:
        return {"reply": _fallback_chat_reply(match_data, analysis_data, question), "provider": "fallback"}

    context = (
        "You are PitchVisionAI, a tactical cricket strategy assistant. Use only the supplied match context. "
        "Answer short, practical cricket questions about tactics, matchups, bowling changes, powerplay plans, and conditions. "
        "Keep answers concise and decision-oriented. Explain uncertainty when conditions or form are unclear. "
        "Never claim certainty about a toss, outcome, injury, or weather event.\n\n"
        f"MATCH CONTEXT:\n{json.dumps(match_data, indent=2)}\n\n"
        f"CURRENT ANALYSIS:\n{json.dumps(analysis_data, indent=2)}\n\n"
        "Return clear tactical advice suitable for a live cricket match situation."
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
            return {"reply": _fallback_chat_reply(match_data, analysis_data, question), "provider": "fallback"}
        return {"reply": answer, "provider": settings["provider"]}
    except (AuthenticationError, RateLimitError, APIConnectionError, APITimeoutError, APIStatusError) as exc:
        current_app.logger.warning("%s chat unavailable: %s", settings["provider"], exc.__class__.__name__)
        return {"reply": _fallback_chat_reply(match_data, analysis_data, question), "provider": "fallback"}
    except Exception as exc:
        current_app.logger.warning("%s chat failed: %s", settings["provider"], exc.__class__.__name__)
        return {"reply": _fallback_chat_reply(match_data, analysis_data, question), "provider": "fallback"}


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
    historical = venue_stats.get("historical") or venue_stats
    first_batting = historical.get("batting_first") or {}
    first_bowling = historical.get("bowling_first") or {}
    score_history = historical.get("scores") or {}
    first_innings = score_history.get("first_innings") or {}
    average_score = first_innings.get("average") or venue_stats.get("avg_score")
    try:
        average_score = int(round(float(average_score))) if average_score is not None else 240
    except (TypeError, ValueError):
        average_score = format_baseline
    else:
        average_score = round((average_score * 0.65) + (format_baseline * 0.35))

    first_win_pct = float(first_batting.get("win_percentage") or venue_stats.get("batting_first_win_pct") or 50)
    second_win_pct = float(first_bowling.get("win_percentage") or venue_stats.get("batting_second_win_pct") or 50)

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
    pitch_reasons = []
    if pitch_type in {"green", "sporting"}:
        pitch_reasons.append("the green or sporting surface should offer early movement, which favors bowling first")
    elif pitch_type in {"dry", "dusty"}:
        pitch_reasons.append("the dry or dusty surface should become harder to score on as it wears, which favors batting first")
    if dew_expected:
        pitch_reasons.append("humidity and likely dew should improve the chase later")
    if rain_probability >= 35:
        pitch_reasons.append(f"rain probability reaches {rain_probability:.0f}%, so using the shorter favorable window matters")
    if first_win_pct >= second_win_pct + 5:
        pitch_reasons.append(f"the venue favors batting first historically ({first_win_pct:.0f}% wins)")
    elif second_win_pct >= first_win_pct + 5:
        pitch_reasons.append(f"the venue favors chasing historically ({second_win_pct:.0f}% wins batting second)")

    bowl_score = 0
    if pitch_type in {"green", "sporting"}: bowl_score += 2
    if dew_expected or rain_probability >= 35: bowl_score += 2
    if second_win_pct >= first_win_pct + 5: bowl_score += 2
    if pitch_type in {"dry", "dusty"}: bowl_score -= 2
    if first_win_pct >= second_win_pct + 5: bowl_score -= 2
    decision = "bowl_first" if bowl_score > 0 else "bat_first"
    decision_reason = "Toss plan: " + "; ".join(pitch_reasons or ["the available venue, pitch, and weather signals are balanced; choose based on player matchups"]) + "."
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
