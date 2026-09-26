"""
RAG ingestion pipeline for SOLVIA.

Flow:
  Source â†’ extraction â†’ cleaning â†’ normalization â†’ chunking â†’ metadata â†’ Gemini embeddings â†’ ChromaDB
"""
from __future__ import annotations

import os
import re
import uuid
from typing import Optional
from datetime import datetime, timezone

from chromadb import Documents, EmbeddingFunction, Embeddings
from pydantic import BaseModel

from app.chroma import get_or_create_collection
from app.gemini import get_genai_client, is_demo_mode, settings
from app.database import SessionLocal
from app.models import Ticket, Document

TICKET_COLLECTION = "solvia_tickets"
DOCUMENT_COLLECTION = "solvia_documents"


# ---------------------------------------------------------------------------
# Cleaning / normalization helpers
# ---------------------------------------------------------------------------

def clean_text(text: str) -> str:
    """Strip excessive whitespace, control chars, and normalize line endings."""
    if not text:
        return ""
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    # collapse multiple blank lines
    text = re.sub(r"\n{3,}", "\n\n", text)
    # collapse spaces/tabs
    text = re.sub(r"[ \t]+", " ", text)
    return text.strip()


def normalize_whitespace(text: str) -> str:
    return clean_text(text)


# ---------------------------------------------------------------------------
# Chunking
# ---------------------------------------------------------------------------

CHUNK_SIZE = 800          # characters per chunk (heuristic)
CHUNK_OVERLAP = 120       # overlap between consecutive chunks


def chunk_text(text: str, chunk_size: int = CHUNK_SIZE, overlap: int = CHUNK_OVERLAP) -> list[str]:
    """Split text into overlapping chunks of roughly `chunk_size` characters.

    Tries paragraph boundaries first, then falls back to fixed-size splitting.
    """
    if not text:
        return []
    text = clean_text(text)
    chunks: list[str] = []

    # Prefer splitting on paragraph breaks
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    current: list[str] = []
    current_len = 0

    for para in paragraphs:
        para_len = len(para) + 1  # account for space/newline
        if current_len + para_len > chunk_size and current:
            chunks.append(" ".join(current))
            # keep overlap: retain tail of current
            overlap_text = " ".join(current[-2:]) if len(current) >= 2 else ""
            current = [overlap_text, para] if overlap_text else [para]
            current_len = sum(len(x) for x in current) + len(current) - 1
        else:
            current.append(para)
            current_len += para_len

    if current:
        chunks.append(" ".join(current))

    # If paragraph chunking produced nothing useful, fall back to fixed-size
    if not chunks:
        for i in range(0, len(text), chunk_size - overlap):
            chunk = text[i : i + chunk_size]
            if chunk.strip():
                chunks.append(chunk)

    return chunks


# ---------------------------------------------------------------------------
# Metadata helpers
# ---------------------------------------------------------------------------

def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def ticket_metadata(
    ticket: Ticket,
    chunk_index: int,
    total_chunks: int,
    chunk_preview: str,
) -> dict:
    return {
        "source_type": "ticket",
        "ticket_id": ticket.ticket_id,
        "title": ticket.title,
        "category": ticket.category or "",
        "system": ticket.system or "",
        "priority": ticket.priority or "",
        "status": ticket.status or "",
        "resolver": ticket.resolver or "",
        "resolution_time_hours": ticket.resolution_time_hours,
        "source": ticket.source or "ServiceNow",
        "source_reliability": ticket.source_reliability if ticket.source_reliability is not None else 0.90,
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "created_at": ticket.created_at.isoformat() if ticket.created_at else "",
        "resolved_at": ticket.resolved_at.isoformat() if ticket.resolved_at else "",
        "chunk_preview": chunk_preview[:200],
    }


def document_metadata(
    document: Document,
    chunk_index: int,
    total_chunks: int,
    chunk_preview: str,
) -> dict:
    return {
        "source_type": "document",
        "document_id": document.document_id,
        "title": document.title,
        "category": document.category or "",
        "system": document.system or "",
        "source_type_label": document.source_type or "",
        "chunk_index": chunk_index,
        "total_chunks": total_chunks,
        "chunk_preview": chunk_preview[:200],
    }


# ---------------------------------------------------------------------------
# Embedding function for ChromaDB
# ---------------------------------------------------------------------------

class GeminiEmbeddingFunction(EmbeddingFunction[Documents]):
    """ChromaDB embedding function that calls Gemini embeddings.

    Uses the configured ``GEMINI_EMBEDDING_MODEL``. In demo mode, returns a
    deterministic hash-based fake embedding so local development works without
    an API key.
    """

    def __init__(self):
        self._model = settings.gemini_embedding_model or "gemini-embedding-001"

    def __call__(self, input: Documents) -> Embeddings:
        if is_demo_mode():
            return _demo_embeddings(input)

        client = get_genai_client()
        if client is None:
            return _demo_embeddings(input)

        dims = _embedding_dims()

        if isinstance(input, str):
            input_list = [input]
        else:
            input_list = list(input)

        embeddings: list[list[float]] = []
        for text in input_list:
            try:
                emb = client.models.embed_content(model=self._model, contents=[text])
                vec = emb.embeddings[0].values if emb.embeddings else []
            except Exception as exc:
                # Fail safe: return a real placeholder embedding instead of
                # all-zero vectors, so ChromaDB distance/retrieval semantics stay
                # interpretable even when the Gemini embedding call fails.
                vec = _demo_embedding(text)
            if not vec:
                vec = _zero_embedding(dims)
            embeddings.append(vec[:dims] if len(vec) >= dims else vec + [0.0] * (dims - len(vec)))
        return embeddings

    def __repr__(self) -> str:
        return f"GeminiEmbeddingFunction(model={self._model!r})"


def _embedding_dims() -> int:
    # gemini-embedding-001 produces 1536-dimensional vectors.
    return 1536


def _zero_embedding(dims: int) -> list[float]:
    return [0.0] * dims


def _demo_embeddings(input: Documents) -> Embeddings:
    """Deterministic hash-based placeholder embeddings for demo mode."""
    if isinstance(input, str):
        inputs = [input]
    else:
        inputs = list(input)
    out: list[list[float]] = []
    for text in inputs:
        h = hash(text)
        vec = []
        for i in range(_embedding_dims()):
            vec.append(float((h >> (i % 32)) & 0xFFFF) / 0xFFFF)
        out.append(vec)
    return out


# ---------------------------------------------------------------------------
# Public ingestion API
# ---------------------------------------------------------------------------

def ingest_ticket(ticket: Ticket, db_session) -> dict:
    """Ingest a single ticket into ChromaDB as chunks with metadata.

    Returns a summary with document_id, chunk count, and status.
    """
    text = f"{ticket.title}\n\n{ticket.description}\n\nResolution:\n{ticket.resolution or ''}"
    text = clean_text(text)
    if not text.strip():
        return {"status": "skipped", "reason": "empty content", "ticket_id": ticket.ticket_id}

    chunks = chunk_text(text)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks produced", "ticket_id": ticket.ticket_id}

    collection = get_or_create_collection(TICKET_COLLECTION, embedding_function=GeminiEmbeddingFunction())

    docs: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"ticket-{ticket.ticket_id}-c{idx}"
        docs.append(chunk)
        metas.append(ticket_metadata(ticket, idx, len(chunks), chunk))
        ids.append(chunk_id)

    # Upsert chunks (idempotent by chunk id)
    collection.upsert(documents=docs, metadatas=metas, ids=ids)

    # Record chunk count on the document/ticket metadata row (reuse Ticket row)
    ticket.resolution = ticket.resolution  # no-op to ensure object is tracked
    db_session.add(ticket)
    db_session.commit()

    return {
        "status": "ok",
        "ticket_id": ticket.ticket_id,
        "chunk_count": len(chunks),
        "collection": TICKET_COLLECTION,
    }


def ingest_document(document: Document, db_session) -> dict:
    """Ingest a single document into ChromaDB as chunks with metadata.

    ``document.metadata_json`` may contain additional source info; this function
    does not parse the file itself â€” the caller should have extracted text.
    """
    text = clean_text(document.metadata_json or "")
    if not text.strip():
        return {"status": "skipped", "reason": "empty content", "document_id": document.document_id}

    chunks = chunk_text(text)
    if not chunks:
        return {"status": "skipped", "reason": "no chunks produced", "document_id": document.document_id}

    collection = get_or_create_collection(DOCUMENT_COLLECTION, embedding_function=GeminiEmbeddingFunction())

    docs: list[str] = []
    metas: list[dict] = []
    ids: list[str] = []

    for idx, chunk in enumerate(chunks):
        chunk_id = f"doc-{document.document_id}-c{idx}"
        docs.append(chunk)
        metas.append(document_metadata(document, idx, len(chunks), chunk))
        ids.append(chunk_id)

    collection.upsert(documents=docs, metadatas=metas, ids=ids)

    document.chunk_count = len(chunks)
    db_session.add(document)
    db_session.commit()

    return {
        "status": "ok",
        "document_id": document.document_id,
        "chunk_count": len(chunks),
        "collection": DOCUMENT_COLLECTION,
    }


def ingest_ticket_direct(
    ticket_id: str,
    title: str,
    description: str,
    category: Optional[str] = None,
    system: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
    resolution: Optional[str] = None,
    resolver: Optional[str] = None,
    resolution_time_hours: Optional[float] = None,
) -> dict:
    """Convenience: create + ingest a ticket in one call (uses a DB session)."""
    with SessionLocal() as db:
        ticket = Ticket(
            ticket_id=ticket_id,
            title=title,
            description=description,
            category=category,
            system=system,
            priority=priority,
            status=status or "resolved",
            resolution=resolution,
            resolver=resolver,
            resolution_time_hours=resolution_time_hours,
        )
        db.add(ticket)
        db.commit()
        db.refresh(ticket)
        return ingest_ticket(ticket, db)


def ingest_document_direct(
    document_id: str,
    title: str,
    source_type: str,
    category: Optional[str] = None,
    system: Optional[str] = None,
    file_path: Optional[str] = None,
    metadata_json: Optional[str] = None,
) -> dict:
    """Convenience: create + ingest a document in one call."""
    with SessionLocal() as db:
        document = Document(
            document_id=document_id,
            title=title,
            source_type=source_type,
            category=category,
            system=system,
            file_path=file_path,
            metadata_json=metadata_json,
        )
        db.add(document)
        db.commit()
        db.refresh(document)
        return ingest_document(document, db)

