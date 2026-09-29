"""
RAG ingestion pipeline for SOLVIA.

Flow:
  Source -> extraction -> cleaning -> chunking -> metadata -> Gemini embeddings -> ChromaDB
"""
from __future__ import annotations

import re
from pathlib import Path

from app.chroma import get_or_create_collection
from app.embeddings import GeminiEmbeddingFunction
from app.models import Document, Ticket
from app.sap_signals import extract_signals, merge_signal_fields, pack_token_chunks, split_heading_blocks

TICKET_COLLECTION = "solvia_tickets"
DOCUMENT_COLLECTION = "solvia_documents"

# ~400 tokens / ~60 token overlap using a 4-chars-per-token heuristic.
CHUNK_TOKENS = 400
CHUNK_OVERLAP_TOKENS = 60


# ---------------------------------------------------------------------------
# Text helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip excessive whitespace, control chars, and normalize line endings."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n{3,}", "\n\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def chunk_text(text: str, chunk_size: int = CHUNK_TOKENS, overlap: int = CHUNK_OVERLAP_TOKENS) -> list[str]:
    """Split on headings/paragraphs, then pack into token-sized overlapping chunks."""
    if not text:
        return []
    blocks = split_heading_blocks(clean_text(text))
    chunks = pack_token_chunks(blocks, target_tokens=chunk_size, overlap_tokens=overlap)
    return [c for c in chunks if c.strip()]


def ticket_chunks(ticket: Ticket) -> list[str]:
    """Keep the resolution attached to every symptom chunk so retrieval never
    returns a problem without its fix.
    """
    symptom = clean_text(f"{ticket.title}\n\n{ticket.description or ''}")
    resolution = clean_text(ticket.resolution or "")
    chunks = chunk_text(symptom) if symptom else []
    if not resolution:
        return chunks
    if not chunks:
        return [f"{symptom}\n\nResolution:\n{resolution}".strip()]
    return [f"{chunk}\n\nResolution:\n{resolution}" for chunk in chunks]


def extract_file_text(path: str | Path, fallback: str = "") -> str:
    file_path = Path(path)
    try:
        if file_path.suffix.lower() == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(str(file_path))
            return clean_text("\n\n".join(page.extract_text() or "" for page in reader.pages))
        return clean_text(file_path.read_text(encoding="utf-8", errors="ignore"))
    except Exception:
        return clean_text(fallback)


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def chroma_meta(values: dict) -> dict:
    """Chroma metadata only accepts str/int/float/bool (no None)."""
    return {
        key: "" if value is None else value if isinstance(value, (bool, int, float)) else str(value)
        for key, value in values.items()
    }


def _iso(value) -> str:
    return value.isoformat() if value else ""


def ticket_signals(ticket: Ticket):
    return merge_signal_fields(
        " ".join([ticket.title or "", ticket.description or "", ticket.resolution or ""]),
        ticket.sap_notes,
        ticket.transactions,
        ticket.error_codes,
    )


def ticket_metadata(ticket: Ticket) -> dict:
    return {
        "source_type": "ticket",
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "category": ticket.category,
        "system": ticket.system,
        "priority": ticket.priority,
        "status": ticket.status,
        "resolver": ticket.resolver,
        "resolution_time_hours": ticket.resolution_time_hours,
        "source": ticket.source or "ServiceNow",
        "source_reliability": ticket.source_reliability if ticket.source_reliability is not None else 0.90,
        "feedback_score": ticket.feedback_score if ticket.feedback_score is not None else 0.5,
        "created_at": _iso(ticket.created_at),
        "resolved_at": _iso(ticket.resolved_at),
        **ticket_signals(ticket).as_meta(),
    }


def document_metadata(document: Document, text: str) -> dict:
    return {
        "source_type": document.source_type or "document",
        "document_id": document.document_id,
        "title": document.title,
        "category": document.category,
        "system": document.system,
        "status": "",
        "feedback_score": 0.5,
        **extract_signals(f"{document.title or ''} {text}").as_meta(),
    }


# ---------------------------------------------------------------------------
# Chroma chunk storage
# ---------------------------------------------------------------------------

def _collection(name: str):
    return get_or_create_collection(name, embedding_function=GeminiEmbeddingFunction())


def _delete_chunks(collection_name: str, id_key: str, source_id: str) -> None:
    try:
        _collection(collection_name).delete(where={id_key: source_id})
    except Exception:
        pass


def _replace_chunks(
    collection_name: str,
    id_key: str,
    id_prefix: str,
    chunks: list[str],
    base_meta: dict,
) -> None:
    """Delete stale chunks for the source, then upsert the fresh ones."""
    source_id = base_meta[id_key]
    _delete_chunks(collection_name, id_key, source_id)
    total = len(chunks)
    _collection(collection_name).upsert(
        ids=[f"{id_prefix}-{source_id}-c{idx}" for idx in range(total)],
        documents=chunks,
        metadatas=[
            chroma_meta({**base_meta, "chunk_index": idx, "total_chunks": total, "chunk_preview": chunk[:200]})
            for idx, chunk in enumerate(chunks)
        ],
    )


def delete_ticket_chunks(ticket_id: str) -> None:
    _delete_chunks(TICKET_COLLECTION, "ticket_id", ticket_id)


def delete_document_chunks(document_id: str) -> None:
    _delete_chunks(DOCUMENT_COLLECTION, "document_id", document_id)


# ---------------------------------------------------------------------------
# Public ingestion API
# ---------------------------------------------------------------------------

def ingest_ticket(ticket: Ticket, db_session) -> dict:
    """Re-embed a ticket into ChromaDB and persist the extracted SAP signals."""
    chunks = ticket_chunks(ticket)
    if not chunks:
        return {"status": "skipped", "reason": "empty content", "ticket_id": ticket.ticket_id}

    for field, value in ticket_signals(ticket).as_meta().items():
        setattr(ticket, field, value or None)
    if ticket.feedback_score is None:
        ticket.feedback_score = 0.5

    _replace_chunks(TICKET_COLLECTION, "ticket_id", "ticket", chunks, ticket_metadata(ticket))
    db_session.add(ticket)
    db_session.commit()

    return {
        "status": "ok",
        "ticket_id": ticket.ticket_id,
        "chunk_count": len(chunks),
        "collection": TICKET_COLLECTION,
        "sap_notes": ticket.sap_notes or "",
        "transactions": ticket.transactions or "",
        "error_codes": ticket.error_codes or "",
    }


def ingest_document(document: Document, db_session) -> dict:
    """Re-embed a document into ChromaDB.

    Text comes from ``document.file_path`` when the file exists, otherwise from
    ``document.metadata_json``.
    """
    text = clean_text(document.metadata_json or "")
    if document.file_path and Path(document.file_path).exists():
        extracted = extract_file_text(document.file_path, fallback=text)
        if extracted:
            text = extracted
            document.metadata_json = extracted

    chunks = chunk_text(text)
    if not chunks:
        return {"status": "skipped", "reason": "empty content", "document_id": document.document_id}

    _replace_chunks(DOCUMENT_COLLECTION, "document_id", "doc", chunks, document_metadata(document, text))
    document.chunk_count = len(chunks)
    db_session.add(document)
    db_session.commit()

    return {
        "status": "ok",
        "document_id": document.document_id,
        "chunk_count": len(chunks),
        "collection": DOCUMENT_COLLECTION,
    }
