export interface SolutionQuery {
  query: string;
  system?: string | null;
  category?: string | null;
  priority?: string | null;
}

export interface EvidenceItem {
  ticket_id?: string | null;
  document_id?: string | null;
  source_type: string;
  title: string;
  snippet: string;
  system?: string | null;
  category?: string | null;
  match_score: number;
  reason: string;
}

export interface ConfidenceBreakdown {
  semantic_similarity: number;
  historical_success_rate: number;
  source_reliability: number;
  recency_factor: number;
}

export interface SolutionResponse {
  solution_title: string;
  match_score: number;
  confidence: string;
  reasoning: string;
  execution_blueprint: string[];
  evidence: EvidenceItem[];
  confidence_breakdown: ConfidenceBreakdown;
  knowledge_gaps: string[];
  requires_human_review: boolean;
}

export interface FeedbackRequest {
  solution_id: string;
  rating: "helpful" | "not_helpful" | "verify_commit";
  notes?: string | null;
}

export interface Feedback {
  id?: number;
  solution_id: string;
  rating: string;
  notes?: string | null;
  created_at?: string | null;
}

export interface AuditEntry {
  id: number;
  event_type: string;
  actor: string;
  detail: string;
  created_at: string;
}

export interface AuditListResponse {
  entries: AuditEntry[];
  total: number;
}

export interface AnalyticsSolutionUsage {
  total_solutions: number;
  by_confidence: Record<string, number>;
  by_feedback: Record<string, number>;
}

export interface AnalyticsFeedbackScores {
  total: number;
  helpful: number;
  not_helpful: number;
  verify_commit: number;
}
