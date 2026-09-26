from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import SolutionUsage, Feedback, AuditLog
from app.schemas import AuditEntry, AuditListResponse

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/solution-usage")
def solution_usage_stats(db: Session = Depends(get_db)):
    """Return high-level solution usage statistics."""
    total = db.execute(select(func.count(SolutionUsage.id))).scalar() or 0
    by_confidence = db.execute(
        select(SolutionUsage.confidence, func.count(SolutionUsage.id))
        .group_by(SolutionUsage.confidence)
    ).all()
    by_feedback = db.execute(
        select(Feedback.rating, func.count(Feedback.id))
        .group_by(Feedback.rating)
    ).all()

    return {
        "total_solutions": total,
        "by_confidence": {k: v for k, v in by_confidence},
        "by_feedback": {k: v for k, v in by_feedback},
    }


@router.get("/feedback-scores")
def feedback_scores(db: Session = Depends(get_db)):
    """Return feedback scoring summary."""
    total = db.execute(select(func.count(Feedback.id))).scalar() or 0
    helpful = db.execute(
        select(func.count(Feedback.id)).where(Feedback.rating == "helpful")
    ).scalar() or 0
    not_helpful = db.execute(
        select(func.count(Feedback.id)).where(Feedback.rating == "not_helpful")
    ).scalar() or 0
    verify_commit = db.execute(
        select(func.count(Feedback.id)).where(Feedback.rating == "verify_commit")
    ).scalar() or 0
    return {
        "total": total,
        "helpful": helpful,
        "not_helpful": not_helpful,
        "verify_commit": verify_commit,
    }


@router.get("/audit")
def audit_events(limit: int = 50, offset: int = 0, event_type: str = None, db: Session = Depends(get_db)):
    stmt = select(AuditLog).order_by(AuditLog.created_at.desc())
    if event_type:
        stmt = stmt.where(AuditLog.event_type == event_type)
    result = db.execute(stmt.offset(offset).limit(limit))
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
