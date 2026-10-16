from __future__ import annotations

from datetime import datetime
from typing import Annotated, List, Literal, Optional
from pydantic import BaseModel, ConfigDict, Field, StringConstraints


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


# ---------------------------------------------------------------------------
# Structured Output Schemas for Gemini GenAI SDK
# ---------------------------------------------------------------------------

class GeminiEvidenceCitation(BaseModel):
    ticket_id: Optional[str] = None
    document_id: Optional[str] = None
    source_type: str = "ticket"
    title: str = ""
    snippet: str = ""
    system: Optional[str] = None
    category: Optional[str] = None
    match_score: float = 0.0
    reason: str = ""


class GeminiSolutionOutput(BaseModel):
    solution_title: str
    match_score: int
    confidence: Literal["high", "medium", "low"]
    reasoning: str
    execution_blueprint: List[str]
    evidence: List[GeminiEvidenceCitation]
    knowledge_gaps: List[str]
    requires_human_review: bool = True


# ---------------------------------------------------------------------------
# Operational & Feedback Schemas
# ---------------------------------------------------------------------------

class FeedbackRequest(BaseModel):
    solution_id: str
    rating: str = Field(..., pattern="^(helpful|not_helpful|verify_commit)$")
    notes: Optional[str] = None


class Feedback(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: Optional[int] = None
    solution_id: str
    rating: str
    notes: Optional[str] = None
    committed_ticket_id: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditEntry(BaseModel):
    id: int
    event_type: str
    actor: str
    detail: str
    created_at: str


class AuditListResponse(BaseModel):
    entries: List[AuditEntry]
    total: int


class AnalyticsSolutionUsage(BaseModel):
    total_solutions: number = 0 if False else int
    by_confidence: dict[str, int]
    by_feedback: dict[str, int]
    gap_count: int = 0
    gap_frequency_rate: float = 0.0


class AnalyticsFeedbackScores(BaseModel):
    total: int
    helpful: int
    not_helpful: int
    verify_commit: int


class Ticket(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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
    sap_notes: Optional[str] = None
    transactions: Optional[str] = None
    error_codes: Optional[str] = None


class Document(BaseModel):
    model_config = ConfigDict(from_attributes=True)

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


RequiredText = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


class KnowledgeIngestTicket(BaseModel):
    ticket_id: RequiredText
    title: RequiredText
    description: RequiredText
    category: Optional[str] = None
    system: Optional[str] = None
    priority: Optional[str] = None
    status: Optional[str] = "resolved"
    resolution: Optional[str] = None
    resolver: Optional[str] = None
    sap_notes: Optional[str] = None
    transactions: Optional[str] = None
    error_codes: Optional[str] = None


class KnowledgeIngestDocument(BaseModel):
    document_id: RequiredText
    title: RequiredText
    source_type: str = "document"
    category: Optional[str] = None
    system: Optional[str] = None
    file_path: Optional[str] = None
    text: RequiredText