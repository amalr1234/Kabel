from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import select, func

from app.database import get_db
from app.models import SolutionUsage, Feedback

router = APIRouter(prefix="/analytics", tags=["analytics"])


def _feedback_by_rating(db: Session) -> dict[str, int]:
    rows = db.execute(
        select(Feedback.rating, func.count(Feedback.id)).group_by(Feedback.rating)
    ).all()
    return {rating: count for rating, count in rows}


@router.get("/solution-usage")
def solution_usage_stats(db: Session = Depends(get_db)):
    """Return high-level solution usage statistics."""
    total = db.execute(select(func.count(SolutionUsage.id))).scalar() or 0
    by_confidence = db.execute(
        select(SolutionUsage.confidence, func.count(SolutionUsage.id))
        .group_by(SolutionUsage.confidence)
    ).all()

    return {
        "total_solutions": total,
        "by_confidence": {k: v for k, v in by_confidence},
        "by_feedback": _feedback_by_rating(db),
    }


@router.get("/feedback-scores")
def feedback_scores(db: Session = Depends(get_db)):
    """Return feedback scoring summary."""
    counts = _feedback_by_rating(db)
    return {
        "total": sum(counts.values()),
        "helpful": counts.get("helpful", 0),
        "not_helpful": counts.get("not_helpful", 0),
        "verify_commit": counts.get("verify_commit", 0),
    }
