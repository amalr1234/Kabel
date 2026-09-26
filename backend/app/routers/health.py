from fastapi import APIRouter

from app.settings import get_settings

settings = get_settings()
router = APIRouter()


@router.get("/health", include_in_schema=True)
def health() -> dict:
    return {
        "status": "ok",
        "service": "SOLVIA",
        "demo_mode": settings.demo_mode,
        "gemini_available": settings.gemini_available,
    }


@router.get("/health/detail", include_in_schema=True)
def health_detail() -> dict:
    return {"status": "ok"}
