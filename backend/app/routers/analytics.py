from collections import Counter
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Feedback, SolutionUsage
from app.schemas import AnalyticsFeedbackScores, AnalyticsSolutionUsage

router = APIRouter(prefix="/analytics", tags=["analytics"])


# @router.get("/solution-usage", response_model=AnalyticsSolutionUsage)
# def get_solution_usage(db: Session = Depends(get_db)):
#     records = db.query(SolutionUsage).all()
#     total = len(records)

#     by_confidence = Counter(r.confidence.lower() for r in records if r.confidence)
#     by_feedback = Counter(r.feedback_rating.lower() for r in records if r.feedback_rating)

#     # Compute knowledge gap occurrences
#     gap_records = sum(1 for r in records if (r.gap_count or 0) > 0)
#     gap_frequency_rate = round((gap_records / total * 100), 1) if total > 0 else 0.0

#     return AnalyticsSolutionUsage(
#         total_solutions=total,
#         by_confidence=dict(by_confidence),
#         by_feedback=dict(by_feedback),
#         gap_count=gap_records,
#         gap_frequency_rate=gap_frequency_rate,
#     )

@router.get("/solution-usage", response_model=AnalyticsSolutionUsage)
def get_solution_usage(db: Session = Depends(get_db)):
    records = db.query(SolutionUsage).all()
    total = len(records)

    by_confidence = Counter(r.confidence.lower() for r in records if r.confidence)
    by_feedback = Counter(r.feedback_rating.lower() for r in records if r.feedback_rating)

    # Safely handle missing or None gap_count values
    gap_records = sum(1 for r in records if getattr(r, "gap_count", 0) and r.gap_count > 0)
    gap_frequency_rate = round((gap_records / total * 100), 1) if total > 0 else 0.0

    return AnalyticsSolutionUsage(
        total_solutions=total,
        by_confidence=dict(by_confidence),
        by_feedback=dict(by_feedback),
        gap_count=gap_records,
        gap_frequency_rate=gap_frequency_rate,
    )


@router.get("/feedback-scores", response_model=AnalyticsFeedbackScores)
def get_feedback_scores(db: Session = Depends(get_db)):
    records = db.query(Feedback).all()
    counts = Counter(r.rating.lower() for r in records if r.rating)

    return AnalyticsFeedbackScores(
        total=len(records),
        helpful=counts.get("helpful", 0),
        not_helpful=counts.get("not_helpful", 0),
        verify_commit=counts.get("verify_commit", 0),
    )