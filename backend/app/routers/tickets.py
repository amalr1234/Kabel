from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select
from typing import List, Optional

from app.crud import find_ticket, get_ticket_or_404
from app.database import get_db
from app.ingest import ingest_ticket
from app.models import Ticket as TicketModel
from app.schemas import Ticket as TicketSchema

router = APIRouter(prefix="/tickets", tags=["tickets"])


@router.get("", response_model=List[TicketSchema])
def list_tickets(
    system: Optional[str] = None,
    category: Optional[str] = None,
    status: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(TicketModel)
    if system:
        stmt = stmt.where(TicketModel.system == system)
    if category:
        stmt = stmt.where(TicketModel.category == category)
    if status:
        stmt = stmt.where(TicketModel.status == status)
    result = db.execute(stmt.order_by(TicketModel.created_at.desc()))
    return result.scalars().all()


@router.get("/{ticket_id}", response_model=TicketSchema)
def get_ticket(ticket_id: str, db: Session = Depends(get_db)):
    return get_ticket_or_404(db, ticket_id)


@router.post("", response_model=TicketSchema, status_code=201)
def create_ticket(ticket: TicketSchema, db: Session = Depends(get_db)):
    if find_ticket(db, ticket.ticket_id):
        raise HTTPException(status_code=409, detail="Ticket ID already exists")

    db_ticket = TicketModel(**ticket.model_dump(exclude={"id"}))
    db.add(db_ticket)
    db.commit()
    db.refresh(db_ticket)
    ingest_ticket(db_ticket, db)
    return db_ticket
