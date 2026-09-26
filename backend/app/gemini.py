from app.settings import get_settings

settings = get_settings()


def build_genai_client():
    from google import genai

    if settings.demo_mode or not settings.gemini_api_key:
        return None

    return genai.Client(api_key=settings.gemini_api_key)


def get_genai_client():
    return build_genai_client()


def is_demo_mode() -> bool:
    return bool(settings.demo_mode or not settings.gemini_api_key)
