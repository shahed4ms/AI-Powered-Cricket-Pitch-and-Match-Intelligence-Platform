from openai import OpenAI
from flask import current_app


def get_ai_settings(api_key=None):
    gemini_key = current_app.config.get("GEMINI_API_KEY")
    if gemini_key and not api_key:
        return {
            "api_key": gemini_key,
            "base_url": current_app.config.get(
                "GEMINI_BASE_URL", "https://generativelanguage.googleapis.com/v1beta/openai/"
            ),
            "model": current_app.config.get("GEMINI_MODEL", "gemini-3.6-flash"),
            "provider": "gemini",
        }

    openai_key = api_key or current_app.config.get("OPENAI_API_KEY")
    if openai_key:
        return {"api_key": openai_key, "base_url": None, "model": "gpt-4o", "provider": "openai"}
    return None


def create_ai_client(settings):
    client_args = {"api_key": settings["api_key"]}
    if settings.get("base_url"):
        client_args["base_url"] = settings["base_url"]
    return OpenAI(**client_args)