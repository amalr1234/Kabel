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
  source?: string | null;
  source_reliability?: number | null;
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

const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

async function json<T>(response: Response): Promise<T> {
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`API error ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

export const api = {
  async solve(query: SolutionQuery): Promise<SolutionResponse> {
    const res = await fetch(`${API_BASE_URL}/search/solve`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(query),
    });
    return json<SolutionResponse>(res);
  },

  async postFeedback(req: FeedbackRequest): Promise<Feedback> {
    const res = await fetch(`${API_BASE_URL}/feedback`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(req),
    });
    return json<Feedback>(res);
  },

  async getFeedbackForSolution(solutionId: string): Promise<Feedback[]> {
    const res = await fetch(`${API_BASE_URL}/feedback/solution/${encodeURIComponent(solutionId)}`);
    return json<Feedback[]>(res);
  },

  async getAudit(limit = 50, offset = 0, eventType?: string | null): Promise<AuditListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (eventType) params.set("event_type", eventType);
    const res = await fetch(`${API_BASE_URL}/audit?${params}`);
    return json<AuditListResponse>(res);
  },

  async getSolutionUsage(): Promise<AnalyticsSolutionUsage> {
    const res = await fetch(`${API_BASE_URL}/analytics/solution-usage`);
    return json<AnalyticsSolutionUsage>(res);
  },

  async getFeedbackScores(): Promise<AnalyticsFeedbackScores> {
    const res = await fetch(`${API_BASE_URL}/analytics/feedback-scores`);
    return json<AnalyticsFeedbackScores>(res);
  },

  async getAuditAnalytics(limit = 50, offset = 0, eventType?: string | null): Promise<AuditListResponse> {
    const params = new URLSearchParams();
    params.set("limit", String(limit));
    params.set("offset", String(offset));
    if (eventType) params.set("event_type", eventType);
    const res = await fetch(`${API_BASE_URL}/analytics/audit?${params}`);
    return json<AuditListResponse>(res);
  },
};
