from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db, SessionLocal
from app.models import AuditLog as AuditLogModel
from app.schemas import AuditEntry, AuditListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


def _write_audit_event(
    db: Session,
    event_type: str,
    actor: str,
    detail: str,
) -> AuditLogModel:
    entry = AuditLogModel(
        event_type=event_type,
        actor=actor,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def record_audit_event(
    event_type: str,
    actor: str,
    detail: str,
) -> dict:
    """
    Internal helper for application code outside FastAPI dependency injection.
    """
    db = SessionLocal()

    try:
        entry = _write_audit_event(
            db=db,
            event_type=event_type,
            actor=actor,
            detail=detail,
        )
        return {
            "id": entry.id,
            "created_at": entry.created_at.isoformat(),
        }
    finally:
        db.close()


@router.post("", status_code=201)
def create_audit_event(
    event_type: str,
    actor: str,
    detail: str,
    db: Session = Depends(get_db),
):
    entry = _write_audit_event(
        db=db,
        event_type=event_type,
        actor=actor,
        detail=detail,
    )
    return {
        "id": entry.id,
        "created_at": entry.created_at.isoformat(),
    }


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(AuditLogModel).order_by(
        AuditLogModel.created_at.desc()
    )

    if event_type:
        stmt = stmt.where(
            AuditLogModel.event_type == event_type
        )

    result = db.execute(
        stmt.offset(offset).limit(limit)
    )

    entries = result.scalars().all()

    return AuditListResponse(
        entries=[
            AuditEntry(
                id=e.id,
                event_type=e.event_type,
                actor=e.actor,
                detail=e.detail,
                created_at=e.created_at.isoformat(),
            )
            for e in entries
        ],
        total=len(entries),
    )