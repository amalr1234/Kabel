from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.query import solve
from app.schemas import SolutionQuery, SolutionResponse

router = APIRouter(prefix="/search", tags=["search"])


@router.post("/solve", response_model=SolutionResponse, status_code=200)
def solve_endpoint(query: SolutionQuery, db: Session = Depends(get_db)):
    try:
        return solve(query, db)
    except Exception as e:
        raise HTTPException(status_code=503, detail=f"SOLVIA engine error: {e}")
