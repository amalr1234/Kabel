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
  solution_id: string;
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
  committed_ticket_id?: string | null;
  created_at?: string | null;
}

export interface KnowledgeStats {
  tickets: number;
  documents: number;
  document_chunks: number;
}

export interface KnowledgeTicket {
  ticket_id: string;
  title: string;
  system?: string | null;
  category?: string | null;
  status?: string | null;
  feedback_score?: number | null;
}

export interface KnowledgeDocument {
  document_id: string;
  title: string;
  source_type: string;
  system?: string | null;
  category?: string | null;
  chunk_count?: number | null;
}

export interface TicketIngestPayload {
  ticket_id: string;
  title: string;
  description: string;
  system?: string;
  category?: string;
  priority?: string;
  status?: string;
  resolution?: string;
  resolver?: string;
  sap_notes?: string;
  transactions?: string;
  error_codes?: string;
}

export interface DocumentIngestPayload {
  document_id: string;
  title: string;
  source_type: string;
  system?: string;
  category?: string;
  text?: string;
}

export interface IngestResult {
  status: string;
  ticket_id?: string;
  document_id?: string;
  chunk_count?: number;
  sap_notes?: string;
  transactions?: string;
  error_codes?: string;
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
  gap_count?: number;
  gap_frequency_rate?: number;
}

export interface AnalyticsFeedbackScores {
  total: number;
  helpful: number;
  not_helpful: number;
  verify_commit: number;
}

export interface HealthCheck {
  ok: boolean;
  error?: string;
  chunks?: number;
}

export interface HealthResponse {
  status: "live" | "demo" | "degraded";
  service: string;
  demo_mode: boolean;
  gemini_available: boolean;
  checks: {
    database: HealthCheck;
    vector_store: HealthCheck;
  };
}

export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export function errorMessage(err: unknown): string {
  return err instanceof Error ? err.message : String(err);
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, init);
  if (!response.ok) {
    const text = await response.text().catch(() => "");
    throw new Error(`API error ${response.status}: ${text}`);
  }
  return response.json() as Promise<T>;
}

function postJson<T>(path: string, body: unknown): Promise<T> {
  return request<T>(path, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
}

const knowledgeItem = (kind: "tickets" | "documents", id: string) =>
  `/knowledge/${kind}/${encodeURIComponent(id)}`;

export const api = {
  getHealth: (signal?: AbortSignal) => request<HealthResponse>("/health", { signal }),

  solve: (query: SolutionQuery) => postJson<SolutionResponse>("/search/solve", query),

  postFeedback: (req: FeedbackRequest) => postJson<Feedback>("/feedback", req),

  getAudit(limit = 50, offset = 0, eventType?: string | null) {
    const params = new URLSearchParams({ limit: String(limit), offset: String(offset) });
    if (eventType) params.set("event_type", eventType);
    return request<AuditListResponse>(`/audit?${params}`);
  },

  getSolutionUsage: () => request<AnalyticsSolutionUsage>("/analytics/solution-usage"),

  getFeedbackScores: () => request<AnalyticsFeedbackScores>("/analytics/feedback-scores"),

  getKnowledgeStats: () => request<KnowledgeStats>("/knowledge/stats"),

  listKnowledgeTickets: () => request<KnowledgeTicket[]>("/knowledge/tickets"),

  listKnowledgeDocuments: () => request<KnowledgeDocument[]>("/knowledge/documents"),

  ingestTicket: (payload: TicketIngestPayload) =>
    postJson<IngestResult>("/knowledge/tickets", payload),

  ingestDocument: (payload: DocumentIngestPayload) =>
    postJson<IngestResult>("/knowledge/documents", payload),

  uploadDocument: (form: FormData) =>
    request<IngestResult>("/knowledge/documents/upload", { method: "POST", body: form }),

  reingestTicket: (ticketId: string) =>
    request<IngestResult>(`${knowledgeItem("tickets", ticketId)}/reingest`, { method: "POST" }),

  reingestDocument: (documentId: string) =>
    request<IngestResult>(`${knowledgeItem("documents", documentId)}/reingest`, { method: "POST" }),

  deleteTicket: (ticketId: string) =>
    request<{ status: string; ticket_id: string }>(knowledgeItem("tickets", ticketId), {
      method: "DELETE",
    }),

  deleteDocument: (documentId: string) =>
    request<{ status: string; document_id: string }>(knowledgeItem("documents", documentId), {
      method: "DELETE",
    }),
};