"""Shared lookups for tickets and documents by their business IDs."""
from __future__ import annotations

from typing import Optional

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Document, Ticket


def find_ticket(db: Session, ticket_id: str) -> Optional[Ticket]:
    return db.execute(select(Ticket).where(Ticket.ticket_id == ticket_id)).scalars().first()


def find_document(db: Session, document_id: str) -> Optional[Document]:
    return db.execute(select(Document).where(Document.document_id == document_id)).scalars().first()


def get_ticket_or_404(db: Session, ticket_id: str) -> Ticket:
    ticket = find_ticket(db, ticket_id)
    if ticket is None:
        raise HTTPException(status_code=404, detail="Ticket not found")
    return ticket


def get_document_or_404(db: Session, document_id: str) -> Document:
    document = find_document(db, document_id)
    if document is None:
        raise HTTPException(status_code=404, detail="Document not found")
    return document
