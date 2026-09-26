from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class SolutionQuery(BaseModel):
    query: str
    system: Optional[str] = None
    category: Optional[str] = None
    priority: Optional[str] = None


class EvidenceItem(BaseModel):
    ticket_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: str
    source: Optional[str] = None
    source_reliability: Optional[float] = None
    title: str
    snippet: str
    system: Optional[str] = None
    category: Optional[str] = None
    match_score: float
    reason: str


class ConfidenceBreakdown(BaseModel):
    semantic_similarity: int
    historical_success_rate: int
    source_reliability: int
    recency_factor: int

    def to_dict(self) -> dict:
        return {
            "semantic_similarity": self.semantic_similarity,
            "historical_success_rate": self.historical_success_rate,
            "source_reliability": self.source_reliability,
            "recency_factor": self.recency_factor,
        }


class SolutionResponse(BaseModel):
    solution_id: str
    solution_title: str
    match_score: int
    confidence: str
    reasoning: str
    execution_blueprint: List[str]
    evidence: List[EvidenceItem]
    confidence_breakdown: ConfidenceBreakdown
    knowledge_gaps: List[str]
    requires_human_review: bool


class FeedbackRequest(BaseModel):
    solution_id: str
    rating: str = Field(..., pattern="^(helpful|not_helpful|verify_commit)$")
    notes: Optional[str] = None


class AuditEntry(BaseModel):
    id: int
    event_type: str
    actor: str
    detail: str
    created_at: str


class AuditListResponse(BaseModel):
    entries: List[AuditEntry]
    total: int


# Ticket and Document schemas mirror the SQLAlchemy models so the API can accept and return them.

class Ticket(BaseModel):
    id: Optional[int] = None
    ticket_id: str
    title: str
    description: str
    category: Optional[str] = None
    system: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = None
    resolution: Optional[str] = None
    created_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolver: Optional[str] = None
    resolution_time_hours: Optional[float] = None
    feedback_score: Optional[float] = None
    source: Optional[str] = None
    source_reliability: Optional[float] = None


    class Config:
        from_attributes = True


class Document(BaseModel):
    id: Optional[int] = None
    document_id: str
    title: str
    source_type: str
    category: Optional[str] = None
    system: Optional[str] = None
    file_path: Optional[str] = None
    chunk_count: Optional[int] = None
    metadata_json: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class Feedback(BaseModel):
    id: Optional[int] = None
    solution_id: str
    rating: str
    notes: Optional[str] = None
    created_at: Optional[datetime] = None

    class Config:
        from_attributes = True
