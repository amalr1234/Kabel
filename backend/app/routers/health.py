from fastapi import APIRouter
from chromadb.errors import NotFoundError
from sqlalchemy import text

from app.chroma import get_chroma_client
from app.database import engine
from app.ingest import DOCUMENT_COLLECTION, TICKET_COLLECTION
from app.settings import get_settings

settings = get_settings()
router = APIRouter()


def _check_database() -> dict:
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return {"ok": True}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def _check_vector_store() -> dict:
    try:
        client = get_chroma_client()
        chunks = 0
        for name in (TICKET_COLLECTION, DOCUMENT_COLLECTION):
            try:
                chunks += client.get_collection(name).count()
            except NotFoundError:
                pass
        return {"ok": True, "chunks": chunks}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


@router.get("/health")
def health() -> dict:
    """Engine status for the UI.

    Gemini is only checked for configuration; calling it here would be billed.
    """
    database = _check_database()
    vector_store = _check_vector_store()

    if not (database["ok"] and vector_store["ok"]):
        status = "degraded"
    elif settings.gemini_available:
        status = "live"
    else:
        status = "demo"

    return {
        "status": status,
        "service": "SOLVIA",
        "demo_mode": settings.demo_mode,
        "gemini_available": settings.gemini_available,
        "checks": {
            "database": database,
            "vector_store": vector_store,
        },
    }
