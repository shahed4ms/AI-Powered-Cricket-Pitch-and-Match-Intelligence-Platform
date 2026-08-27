import base64, json
from openai import APIConnectionError, APIStatusError, APITimeoutError, AuthenticationError, OpenAI, RateLimitError
from flask import current_app
from app.services.ai_provider import create_ai_client, get_ai_settings


def analyze_pitch_image(image_path, api_key=None):
    settings = get_ai_settings(api_key)
    if not settings:
        return {"error": "No AI provider key configured"}

    try:
        with open(image_path, "rb") as f:
            image_data = base64.b64encode(f.read()).decode("utf-8")
    except OSError:
        current_app.logger.warning("Pitch analysis unavailable: image could not be read")
        return {"error": "Pitch image could not be read"}

    ext = image_path.rsplit(".", 1)[-1].lower()
    mime = "image/png" if ext == "png" else "image/jpeg"

    try:
        client = create_ai_client(settings)
        response = client.chat.completions.create(
            model=settings["model"],
            messages=[
                {
                    "role": "system",
                    "content": (
                        "You are an expert cricket pitch analyst. Analyze the provided pitch image "
                        "and return a JSON object with the following fields:\n"
                        "- pitch_type: one of 'green', 'dry', 'dusty', 'dead', 'sporting', 'unknown'\n"
                        "- bounce_estimate: one of 'high', 'medium', 'low'\n"
                        "- bounce_percentage: integer 0-100\n"
                        "- spin_estimate: one of 'high', 'medium', 'low'\n"
                        "- spin_percentage: integer 0-100\n"
                        "- surface_condition: one of 'cracked', 'smooth', 'abrasive', 'moist'\n"
                        "- grass_coverage: one of 'none', 'sparse', 'moderate', 'heavy'\n"
                        "- confidence: integer 0-100\n"
                        "- reasoning: brief explanation\n\n"
                        "Return ONLY valid JSON, no other text."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Analyze this cricket pitch image."},
                        {"type": "image_url", "image_url": {"url": f"data:{mime};base64,{image_data}"}},
                    ],
                },
            ],
            max_tokens=1000,
            response_format={"type": "json_object"},
        )
    except AuthenticationError:
        current_app.logger.warning("%s pitch analysis unavailable: authentication failed", settings["provider"])
        return {"error": f"{settings['provider'].title()} authentication failed. Check its API key."}
    except RateLimitError:
        current_app.logger.warning("OpenAI pitch analysis unavailable: rate limit reached")
        return {"error": "AI provider rate limit reached. Try again later."}
    except (APIConnectionError, APITimeoutError):
        current_app.logger.warning("OpenAI pitch analysis unavailable: connection or timeout")
        return {"error": "AI provider could not be reached."}
    except APIStatusError as exc:
        current_app.logger.warning("OpenAI pitch analysis unavailable: status=%s", exc.status_code)
        return {"error": "AI provider returned an error."}
    except Exception as exc:
        current_app.logger.warning("OpenAI pitch analysis unavailable: %s", exc.__class__.__name__)
        return {"error": "AI pitch analysis failed."}

    raw = response.choices[0].message.content.strip()
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        current_app.logger.warning("%s pitch analysis unavailable: response was not valid JSON", settings["provider"])
        return {"error": "AI provider returned an invalid pitch response."}
