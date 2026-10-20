from typing import Optional

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func, select

from app.database import get_db, SessionLocal
from app.models import AuditLog as AuditLogModel
from app.schemas import AuditEntry, AuditListResponse

router = APIRouter(prefix="/audit", tags=["audit"])


def _write_audit_event(
    db: Session,
    event_type: str,
    actor: str,
    detail: str,
) -> dict:
    entry = AuditLogModel(
        event_type=event_type,
        actor=actor,
        detail=detail,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return {
        "id": entry.id,
        "created_at": entry.created_at.isoformat(),
    }


def record_audit_event(
    event_type: str,
    actor: str,
    detail: str,
) -> dict:
    """
    Internal helper for application code outside FastAPI dependency injection.
    """
    with SessionLocal() as db:
        return _write_audit_event(db, event_type, actor, detail)


@router.post("", status_code=201)
def create_audit_event(
    event_type: str,
    actor: str,
    detail: str,
    db: Session = Depends(get_db),
):
    return _write_audit_event(db, event_type, actor, detail)


@router.get("", response_model=AuditListResponse)
def list_audit_events(
    limit: int = 50,
    offset: int = 0,
    event_type: Optional[str] = None,
    db: Session = Depends(get_db),
):
    stmt = select(AuditLogModel)
    if event_type:
        stmt = stmt.where(AuditLogModel.event_type == event_type)

    total = db.execute(select(func.count()).select_from(stmt.subquery())).scalar() or 0
    entries = db.execute(
        stmt.order_by(AuditLogModel.created_at.desc()).offset(offset).limit(limit)
    ).scalars().all()

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
        total=total,
    )
