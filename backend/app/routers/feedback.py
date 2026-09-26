from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from typing import List

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import select

from app.database import get_db
from app.models import Feedback as FeedbackModel
from app.schemas import FeedbackRequest, Feedback as FeedbackSchema

router = APIRouter(prefix="/feedback", tags=["feedback"])


@router.post("", response_model=FeedbackSchema, status_code=201)
def record_feedback(req: FeedbackRequest, db: Session = Depends(get_db)):
    db_feedback = FeedbackModel(**req.model_dump(mode="json"))
    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)
    return db_feedback


@router.get("/solution/{solution_id}", response_model=List[FeedbackSchema])
def get_feedback_for_solution(solution_id: str, db: Session = Depends(get_db)):
    result = db.execute(
        select(FeedbackModel).where(FeedbackModel.solution_id == solution_id)
    ).scalars().all()
    return result
