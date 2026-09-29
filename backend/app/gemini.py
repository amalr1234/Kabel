from functools import lru_cache

from app.settings import get_settings

settings = get_settings()


def is_demo_mode() -> bool:
    return not settings.gemini_available


@lru_cache(maxsize=1)
def get_genai_client():
    """Return a shared Gemini client, or ``None`` in demo mode / without an API key."""
    if is_demo_mode():
        return None

    from google import genai

    return genai.Client(api_key=settings.gemini_api_key)
