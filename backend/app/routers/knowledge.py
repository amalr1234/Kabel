from __future__ import annotations

import shutil
import uuid
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.crud import find_document, find_ticket, get_document_or_404, get_ticket_or_404
from app.database import get_db
from app.ingest import (
    delete_document_chunks,
    delete_ticket_chunks,
    extract_file_text,
    ingest_document,
    ingest_ticket,
)
from app.models import Document as DocumentModel
from app.models import Ticket as TicketModel
from app.schemas import Document as DocumentSchema
from app.schemas import KnowledgeIngestDocument, KnowledgeIngestTicket, Ticket as TicketSchema

router = APIRouter(prefix="/knowledge", tags=["knowledge"])

UPLOAD_DIR = Path(__file__).resolve().parents[1] / "uploads"
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)


@router.get("/stats")
def knowledge_stats(db: Session = Depends(get_db)):
    tickets = db.execute(select(func.count(TicketModel.id))).scalar() or 0
    documents = db.execute(select(func.count(DocumentModel.id))).scalar() or 0
    chunks = db.execute(select(func.coalesce(func.sum(DocumentModel.chunk_count), 0))).scalar() or 0
    return {
        "tickets": tickets,
        "documents": documents,
        "document_chunks": int(chunks),
    }


@router.get("/tickets", response_model=list[TicketSchema])
def list_knowledge_tickets(db: Session = Depends(get_db)):
    return db.execute(select(TicketModel).order_by(TicketModel.created_at.desc())).scalars().all()


@router.get("/documents", response_model=list[DocumentSchema])
def list_knowledge_documents(db: Session = Depends(get_db)):
    return db.execute(select(DocumentModel).order_by(DocumentModel.created_at.desc())).scalars().all()


@router.post("/tickets")
def ingest_knowledge_ticket(payload: KnowledgeIngestTicket, db: Session = Depends(get_db)):
    ticket = find_ticket(db, payload.ticket_id)
    if ticket is None:
        ticket = TicketModel()
        db.add(ticket)

    for field, value in payload.model_dump().items():
        setattr(ticket, field, value)
    ticket.status = payload.status or "resolved"
    db.commit()
    db.refresh(ticket)
    return ingest_ticket(ticket, db)


@router.post("/documents")
def ingest_knowledge_document(payload: KnowledgeIngestDocument, db: Session = Depends(get_db)):
    document = find_document(db, payload.document_id)
    if document is None:
        document = DocumentModel()
        db.add(document)

    for field, value in payload.model_dump(exclude={"text"}).items():
        setattr(document, field, value)
    document.metadata_json = payload.text
    db.commit()
    db.refresh(document)
    return ingest_document(document, db)


@router.post("/documents/upload")
async def upload_knowledge_document(
    file: UploadFile = File(...),
    title: Optional[str] = Form(None),
    source_type: str = Form("pdf"),
    system: Optional[str] = Form(None),
    category: Optional[str] = Form(None),
    document_id: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    suffix = Path(file.filename or "note.txt").suffix.lower() or ".txt"
    stored_id = (document_id or "").strip() or f"DOC-{uuid.uuid4().hex[:10].upper()}"
    dest = UPLOAD_DIR / f"{stored_id}{suffix}"
    with dest.open("wb") as handle:
        shutil.copyfileobj(file.file, handle)

    extracted = extract_file_text(dest)
    if not extracted.strip():
        dest.unlink(missing_ok=True)
        raise HTTPException(status_code=400, detail="Could not extract text from the uploaded file")

    payload = KnowledgeIngestDocument(
        document_id=stored_id,
        title=title or Path(file.filename or stored_id).stem,
        source_type=source_type or suffix.lstrip(".") or "document",
        category=category,
        system=system,
        file_path=str(dest),
        text=extracted,
    )
    return ingest_knowledge_document(payload, db)


@router.post("/tickets/{ticket_id}/reingest")
def reingest_ticket(ticket_id: str, db: Session = Depends(get_db)):
    return ingest_ticket(get_ticket_or_404(db, ticket_id), db)


@router.post("/documents/{document_id}/reingest")
def reingest_document(document_id: str, db: Session = Depends(get_db)):
    return ingest_document(get_document_or_404(db, document_id), db)


@router.delete("/tickets/{ticket_id}")
def delete_knowledge_ticket(ticket_id: str, db: Session = Depends(get_db)):
    ticket = get_ticket_or_404(db, ticket_id)
    delete_ticket_chunks(ticket_id)
    db.delete(ticket)
    db.commit()
    return {"status": "deleted", "ticket_id": ticket_id}


def _remove_uploaded_file(stored: Optional[str]) -> None:
    """Delete a file only if it lives inside UPLOAD_DIR (never user-supplied paths elsewhere)."""
    if not stored:
        return
    path = Path(stored).resolve()
    if path.is_relative_to(UPLOAD_DIR.resolve()):
        path.unlink(missing_ok=True)


@router.delete("/documents/{document_id}")
def delete_knowledge_document(document_id: str, db: Session = Depends(get_db)):
    document = get_document_or_404(db, document_id)
    delete_document_chunks(document_id)
    stored = document.file_path
    db.delete(document)
    db.commit()
    _remove_uploaded_file(stored)
    return {"status": "deleted", "document_id": document_id}
