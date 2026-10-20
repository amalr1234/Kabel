from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from app.crud import find_document, get_document_or_404
from app.database import get_db
from app.ingest import ingest_document
from app.models import Document as DocumentModel
from app.schemas import Document as DocumentSchema

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=List[DocumentSchema])
def list_documents(
    system: Optional[str] = None,
    category: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(DocumentModel)
    if system:
        stmt = stmt.where(DocumentModel.system == system)
    if category:
        stmt = stmt.where(DocumentModel.category == category)
    result = db.execute(stmt.order_by(DocumentModel.created_at.desc()))
    return result.scalars().all()


@router.get("/{document_id}", response_model=DocumentSchema)
def get_document(document_id: str, db: Session = Depends(get_db)):
    return get_document_or_404(db, document_id)


@router.post("", response_model=DocumentSchema, status_code=201)
def create_document(doc: DocumentSchema, db: Session = Depends(get_db)):
    if find_document(db, doc.document_id):
        raise HTTPException(status_code=409, detail="Document ID already exists")

    db_doc = DocumentModel(**doc.model_dump(exclude={"id"}))
    db.add(db_doc)
    db.commit()
    db.refresh(db_doc)
    ingest_document(db_doc, db)
    return db_doc
