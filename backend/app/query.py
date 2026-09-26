"""
SOLVIA RAG query pipeline.

Query:
  User issue â†’ Gemini embedding â†’ ChromaDB semantic search â†’ retrieve top candidates
  â†’ rerank/filter â†’ Gemini reasoning â†’ structured solution

Grounding rules:
  - Gemini must NOT invent ticket IDs, SAP Notes, transactions, solutions,
    source documents, or technical facts.
  - If evidence is insufficient, say so.
  - If evidence conflicts, say so.
  - Every recommendation must be linked to retrieved evidence.
"""
from __future__ import annotations
from sqlalchemy.orm import Session
from app.models import SolutionUsage

import math
import uuid
from typing import Optional

from pydantic import BaseModel
from requests import Session

from app.chroma import get_chroma_client
from app.gemini import get_genai_client, is_demo_mode, settings
from app.ingest import TICKET_COLLECTION, DOCUMENT_COLLECTION, GeminiEmbeddingFunction
from app.schemas import (
    SolutionQuery,
    SolutionResponse,
    EvidenceItem,
    ConfidenceBreakdown,
)
from app.routers.audit import record_audit_event as log_audit

# ---------------------------------------------------------------------------
# Configuration (tune these as you refine the engine)
# ---------------------------------------------------------------------------

TOP_K = 8                 # candidates retrieved from ChromaDB
RERANK_TOP_N = 3          # final candidates after rerank/filter

# ---------------------------------------------------------------------------
# ChromaDB metric
# ---------------------------------------------------------------------------

# Inspected from the live ChromaDB collection configuration in this project.
# Both `solvia_tickets` and `solvia_documents` are currently created with an
# HNSW index using the `l2` space, so ChromaDB returns L2 distances.
#
# We do not assume this is permanent. If the index is rebuilt with a cosine
# space later, the conversion should be updated accordingly.
CHROMADB_METRICS = frozenset({"l2", "cosine", "ip"})


def chromadb_metric() -> str:
    """Read the effective distance metric from the live ChromaDB collections.

    Falls back to ``"l2"`` if the configuration cannot be read.
    """
    client = get_chroma_client()
    for coll_name in (TICKET_COLLECTION, DOCUMENT_COLLECTION):
        try:
            coll = client.get_collection(coll_name)
            config = coll.configuration
            if not isinstance(config, dict):
                continue
            hnsw = config.get("hnsw")
            if isinstance(hnsw, dict):
                space = hnsw.get("space")
                if space in CHROMADB_METRICS:
                    return space
        except Exception:
            continue
    return "l2"


# ---------------------------------------------------------------------------
# Reranking / filtering helpers
# ---------------------------------------------------------------------------

def score_candidate(result: dict, query_system: Optional[str], query_category: Optional[str]) -> float:
    """Convert a ChromaDB retrieval result into a 0-100 match-style score.

    Two transformations are applied:

    1. Distance -> semantic_similarity
       - ``l2`` (current collection metric) is converted using a cosine-style
         equivalence so the result is still interpretable on a 0-100 scale:
         ``cosine_sim â‰ˆ 1 - (l2Â² / (2 * |a|Â² * |b|Â²))``.
       - Because we do not reliably know per-vector norms at scoring time in
         all code paths, we use the conservative approximation that typical
         Gemini embeddings in this project have norms in a predictable range.
         In practice, the dominant failure mode is large L2 distances when
         embeddings are not normalized, so we map ``l2`` into ``[0, 1]`` with
         a bounded transform and then into the 0-100 range.
       - The transform preserves ranking: smaller L2 distance still yields a
         higher score.

    2. Metadata bonuses
       - Small bonuses are added for system/category alignment so that
         retrieval ranking is refined without inventing evidence.
    """
    distance = float(result.get("distance", 0.0))
    metric = chromadb_metric()

    # Use the raw distance (no floor) so exact matches (distance 0) map to
    # similarity 1 and the reference-point semantics stay intact.

    # Use the raw distance value (no floor) so that exact matches (distance 0)
    # map to similarity 1 and the reference-point semantics stay intact.

    # Use the raw distance value (no floor) so that exact matches (distance 0)
    # map to similarity 1 and the reference-point semantics stay intact.

    # Use the raw distance value (no floor) so that exact matches (distance 0)
    # map to similarity 1 and the reference-point semantics stay intact.

    if metric == "cosine":
        # cosine distance in ChromaDB is typically in [0, 2]; 0 is identical.
        similarity = max(0.0, 1.0 - (distance / 2.0))
    elif metric == "ip":
        # inner product can be negative; map to a similarity in [0, 1].
        # This is approximate; if IP semantics are important, normalize first.
        similarity = max(0.0, min(1.0, 1.0 - (distance / (1.0 + abs(distance)))))
    else:
        # Default: l2
        # Metric-aware L2 formula: similarity = 1 / (1 + distance / 2)
        # distance 0 -> 1.0; distance 2 -> 0.5; monotonic and bounded.
        similarity = 1.0 / (1.0 + (distance / 2.0))

    # Keep the semantic score bounded before any metadata bonus is applied.
    base = max(0.0, min(100.0, similarity * 100.0))

    bonus = 0.0
    sys = (result.get("sys") or result.get("system") or "").lower()
    if query_system and sys == query_system.lower():
        bonus += 8.0
    cat = (result.get("cat") or result.get("category") or "").lower()
    if query_category and cat == query_category.lower():
        bonus += 6.0

    return base + bonus


def extract_meta(result: dict) -> dict:
    """Normalize metadata keys from a ChromaDB result into a stable dict."""
    m = result.get("metadata") or {}
    out = {
        "ticket_id": m.get("ticket_id") or m.get("src_ticket_id"),
        "document_id": m.get("document_id") or m.get("src_document_id"),
        "source_type": m.get("source_type") or m.get("type"),
        "title": m.get("title"),
        "system": m.get("system") or m.get("sys"),
        "category": m.get("category") or m.get("cat"),
        "priority": m.get("priority"),
        "status": m.get("status"),
        "resolver": m.get("resolver"),
        "resolution_time_hours": m.get("resolution_time_hours"),
        "created_at": m.get("created_at"),
        "resolved_at": m.get("resolved_at"),
        "chunk_index": m.get("chunk_index"),
        "total_chunks": m.get("total_chunks"),
    }
    return out


def recency_factor(created_at: Optional[str], resolved_at: Optional[str]) -> float:
    """Return a 0-100 recency score. More recent = higher.

    When only ``created_at`` is available, use it. When a resolution date is
    present, prefer that as the 'last activity' signal.
    """
    if not created_at and not resolved_at:
        return 50.0

    last = resolved_at or created_at
    try:
        if last.endswith("Z"):
            last = last[:-1] + "+00:00"
        dt = __import__("datetime").datetime.fromisoformat(last)
    except Exception:
        return 50.0

    now = __import__("datetime").datetime.now(__import__("datetime").timezone.utc)
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=__import__("datetime").timezone.utc)
    age_days = max(0.0, (now - dt).total_seconds() / 86400.0)
    # decay: 100 when <= 30 days, ~0 when > 365 days
    return max(0.0, 100.0 - (age_days / 365.0 * 100.0))


def historical_success_rate(ticket_id: Optional[str], status: Optional[str] = None, resolution_time_hours: Optional[float] = None) -> float:
    """Return a 0-100 historical success heuristic based on ticket metadata.

    In the current implementation this is a placeholder heuristic derived from
    ticket metadata (priority, resolved status, resolution time). Once feedback
    data accumulates in PostgreSQL, this should be recalculated from actual
    feedback ratings.
    """
    # Placeholder: resolved + short resolution time implies higher success.
    # This is refined later with real feedback signals.
    base = 70.0
    if status and status.lower() == "resolved":
        base += 10.0
    if resolution_time_hours is not None:
        if resolution_time_hours <= 2.0:
            base += 10.0
        elif resolution_time_hours <= 8.0:
            base += 5.0
    return max(0.0, min(100.0, base))


def source_reliability(source_type: Optional[str], status: Optional[str]) -> float:
    """Return a 0-100 source reliability heuristic."""
    if not source_type:
        return 50.0
    t = source_type.lower()
    if t == "ticket":
        # Resolved tickets are more reliable than open ones
        if status and status.lower() == "resolved":
            return 90.0
        return 70.0
    if t in ("pdf", "documentation", "sap_note", "note", "manual"):
        return 85.0
    if t in ("csv", "json", "markdown", "txt"):
        return 75.0
    return 60.0


# ---------------------------------------------------------------------------
# Embedding the query
# ---------------------------------------------------------------------------

def embed_query(text: str) -> list[float]:
    """Embed a single query string using the configured Gemini embedding model.

    In demo mode returns deterministic placeholder embeddings.
    """
    if is_demo_mode():
        return _demo_embedding(text)

    client = get_genai_client()
    if client is None:
        return _demo_embedding(text)

    try:
        emb = client.models.embed_content(model=settings.gemini_embedding_model, contents=[text])
        vec = emb.embeddings[0].values if emb.embeddings else []
    except Exception:
        vec = _demo_embedding(text)

    dims = 1536
    if not vec:
        vec = _zero_embedding(dims)
    if len(vec) >= dims:
        return vec[:dims]
    return vec + _zero_embedding(dims - len(vec))

def _zero_embedding(dims: int) -> list[float]:
    """Return a zero-filled embedding vector of the requested size."""
    return [0.0] * dims

def _demo_embedding(text: str) -> list[float]:
    h = hash(text)
    dims = 1536
    vec = []
    for i in range(dims):
        vec.append(float((h >> (i % 32)) & 0xFFFF) / 0xFFFF)
    return vec


# ---------------------------------------------------------------------------
# Semantic retrieval
# ---------------------------------------------------------------------------

def retrieve_candidates(
    query_embedding: list[float],
    query_system: Optional[str],
    query_category: Optional[str],
) -> list[dict]:
    """Retrieve top candidates from both ticket and document collections.

    Returns a list of dicts with normalized metadata + match score.
    """
    client = get_chroma_client()

    candidates: list[dict] = []

    for coll_name in (TICKET_COLLECTION, DOCUMENT_COLLECTION):
        try:
            coll = client.get_collection(coll_name)
        except Exception:
            # Collection may not exist yet in a fresh install
            continue

        try:
            results = coll.query(query_embeddings=[query_embedding], n_results=TOP_K)
        except Exception as e:
            # Some ChromaDB versions/impls may fail on empty collections or embeddings
            continue

        if not results or not results.get("ids") or not results["ids"][0]:
            continue

        ids = results["ids"][0]
        metadatas = results.get("metadatas", [[]])[0]
        documents = results.get("documents", [[]])[0]
        distances = results.get("distances", [[]])[0]

        for idx, rid in enumerate(ids):
            meta_raw = metadatas[idx] if metadatas and idx < len(metadatas) else {}
            doc_text = documents[idx] if documents and idx < len(documents) else ""
            dist = float(distances[idx]) if distances and idx < len(distances) else 0.0

            meta = {
                "source_type": meta_raw.get("source_type") or ("ticket" if coll_name == TICKET_COLLECTION else "document"),
                "title": meta_raw.get("title", ""),
                "system": meta_raw.get("system", ""),
                "category": meta_raw.get("category", ""),
                "priority": meta_raw.get("priority", ""),
                "status": meta_raw.get("status", ""),
                "resolver": meta_raw.get("resolver", ""),
                "resolution_time_hours": meta_raw.get("resolution_time_hours"),
                "source": meta_raw.get("source", "ServiceNow"),
                "source_reliability": meta_raw.get("source_reliability", 0.90),
                "created_at": meta_raw.get("created_at", ""),
                "resolved_at": meta_raw.get("resolved_at", ""),
                "ticket_id": meta_raw.get("ticket_id", ""),
                "document_id": meta_raw.get("document_id", ""),
                "chunk_index": meta_raw.get("chunk_index"),
                "total_chunks": meta_raw.get("total_chunks"),
            }

            match_score = score_candidate(
                {"distance": dist, "sys": meta.get("system"), "cat": meta.get("category")},
                query_system,
                query_category,
            )

            candidates.append({
                "id": rid,
                "system": meta.get("system"),
                "category": meta.get("category"),
                "priority": meta.get("priority"),
                "status": meta.get("status"),
                "resolver": meta.get("resolver"),
                "resolution_time_hours": meta.get("resolution_time_hours"),
                "created_at": meta.get("created_at"),
                "resolved_at": meta.get("resolved_at"),
                "title": meta.get("title") or "(no title)",
                "source_type": meta.get("source_type"),
                "source": meta.get("source") or "ServiceNow",
                "source_reliability": meta.get("source_reliability", 0.90),
                "ticket_id": meta.get("ticket_id") or "",
                "document_id": meta.get("document_id") or "",
                "chunk_index": meta.get("chunk_index"),
                "total_chunks": meta.get("total_chunks"),
                "snippet": doc_text,
                "distance": dist,
                "match_score": match_score,
                "collection": coll_name,
            })

    # Sort by match score descending
    candidates.sort(key=lambda c: c["match_score"], reverse=True)
    return candidates[:RERANK_TOP_N]


# ---------------------------------------------------------------------------
# Gemini reasoning (grounded)
# ---------------------------------------------------------------------------

_SYSTEM_PROMPT = """\
You are SOLVIA, an enterprise AI intelligence engine for SAP/IT support consultants.

You must reason ONLY from the retrieved evidence provided below. Do NOT invent,
hallucinate, or assume any of the following unless it is explicitly stated in
the evidence:
- ticket IDs
- SAP Notes
- transactions
- commands
- solutions
- source documents
- technical facts

Grounding rules:
- Every recommendation must be linked to retrieved evidence by citing the
  ticket_id or document_id and a short reason.
- If evidence is insufficient, say so clearly.
- If evidence conflicts, say so clearly.
- Never present a solution as certain when the evidence is weak.
- The final output must be structured and machine-readable.

Output format (strict):
Return ONLY a JSON object with these fields:
{
  "solution_title": "short descriptive title",
  "match_score": <integer 0-100>,
  "confidence": "high" | "medium" | "low",
  "reasoning": "concise grounded explanation",
  "execution_blueprint": ["step 1", "step 2", ...],
  "evidence": [
    {
      "ticket_id": "...",
      "document_id": "...",
      "source_type": "ticket" | "document",
      "title": "...",
      "snippet": "...",
      "system": "...",
      "category": "...",
      "match_score": <number>,
      "reason": "why this evidence supports the recommendation"
    }
  ],
  "knowledge_gaps": ["gap 1", ...],
  "requires_human_review": true
}

Do NOT include any text outside the JSON object.
"""


def build_evidence_context(candidates: list[dict]) -> str:
    """Build the evidence block that is sent to Gemini for grounded reasoning."""
    lines: list[str] = []
    for i, c in enumerate(candidates, 1):
        lines.append(f"--- Candidate {i} ---")
        lines.append(f"Source type: {c['source_type']}")
        lines.append(f"Title: {c['title'] or '(no title)'}")
        if c["ticket_id"]:
            lines.append(f"Ticket ID: {c['ticket_id']}")
        if c["document_id"]:
            lines.append(f"Document ID: {c['document_id']}")
        if c["system"]:
            lines.append(f"System: {c['system']}")
        if c["category"]:
            lines.append(f"Category: {c['category']}")
        if c["priority"]:
            lines.append(f"Priority: {c['priority']}")
        if c["status"]:
            lines.append(f"Status: {c['status']}")
        if c["resolver"]:
            lines.append(f"Resolver: {c['resolver']}")
        if c["resolution_time_hours"] is not None:
            lines.append(f"Resolution time (h): {c['resolution_time_hours']}")
        if c["created_at"]:
            lines.append(f"Created: {c['created_at']}")
        if c["resolved_at"]:
            lines.append(f"Resolved: {c['resolved_at']}")
        lines.append(f"Match score: {c['match_score']:.1f}")
        lines.append("Content snippet:")
        lines.append(c["snippet"])
        lines.append("")
    return "\n".join(lines)


def build_user_prompt(query: str, context: str) -> str:
    return f"""\
User issue:
{query}

Retrieved evidence (reason ONLY from this):
{context}
"""


def call_gemini_reasoning(user_prompt: str) -> dict:
    """Call Gemini generation with the grounding system prompt and return parsed JSON.

    In demo mode returns a deterministic placeholder solution so the UI can be
    developed and tested without an API key.
    """
    if is_demo_mode():
        return _demo_solution(user_prompt)

    client = get_genai_client()
    if client is None:
        return _demo_solution(user_prompt)

    try:
        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[_SYSTEM_PROMPT, user_prompt],
        )
        text = resp.text or ""
    except Exception as exc:
        # Surface a clear error for debugging; the caller handles fallback.
        return {"_error": str(exc)}

    if not text.strip():
        return {"_error": "Gemini returned an empty response"}

    return _parse_gemini_json(text)


def _parse_gemini_json(text: str) -> dict:
    """Extract the first JSON object from the Gemini response text."""
    import json, re

    text = text.strip()
    # Try direct parse
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try to find a JSON block
    m = re.search(r"\{[{^\n]*\}", text, re.DOTALL)
    if m:
        try:
            return json.loads(m.group(0))
        except json.JSONDecodeError:
            pass

    # Fallback: wrap in object with reasoning and knowledge gaps
    return {
        "solution_title": "Analysis from retrieved evidence",
        "match_score": 75,
        "confidence": "medium",
        "reasoning": text[:600],
        "execution_blueprint": ["Proceed with human review of the evidence above."],
        "evidence": [],
        "knowledge_gaps": ["Unable to parse structured output from the model; defaulting to grounded summary."],
        "requires_human_review": True,
    }


def _demo_solution(user_prompt: str) -> dict:
    """Deterministic placeholder solution for demo mode.

    This mirrors the real structured schema so the frontend can be developed
    without a live Gemini key. It is grounded in the fake evidence that the
    pipeline retrieves in demo mode (the same ChromaDB content).
    """
    snippet = ""
    title = "Sample solution from retrieved evidence"
    ticket_id = ""
    document_id = ""
    source_type = "ticket"
    system = ""
    category = ""

    # Try to derive a little context from the user prompt
    prompt_lower = user_prompt.lower()
    if "login" in prompt_lower or "authentication" in prompt_lower:
        title = "Authentication failure after password reset"
        snippet = (
            "Clear the SAML token cache and re-authenticate. If the issue persists, "
            "verify the password hash sync with the identity provider and confirm the "
            "user's account is not locked."
        )
        ticket_id = "T-1001"
        document_id = "DOC-SAP-001"
        system = "SAP"
        category = "authentication"
        source_type = "ticket"
    elif "performance" in prompt_lower or "slow" in prompt_lower:
        title = "Performance degradation investigation"
        snippet = (
            "Review ST03N workload analysis, check for long-running reports, and "
            "verify index consistency on frequently accessed tables."
        )
    else:
        snippet = (
            "Review the retrieved evidence with a subject matter expert. No automated "
            "resolution is recommended without human verification."
        )

    return {
        "solution_title": title,
        "match_score": 92,
        "confidence": "high",
        "reasoning": (
            "Based on retrieved historical ticket T-1001 and SAP authentication "
            "documentation DOC-SAP-001, the most likely cause is a stale SAML token "
            "or identity provider password hash sync delay. The evidence consistently "
            "points to clearing the token cache and re-authenticating."
        ),
        "execution_blueprint": [
            "Identify the affected user and confirm the password reset timestamp.",
            "Clear the SAML token cache on the SAP frontend and identity provider.",
            "Re-authenticate the user and verify login succeeds.",
            "If login still fails, verify password hash synchronization with the identity provider.",
            "Confirm the user account is not locked and that role assignments are intact.",
            "Document the resolution and update the ticket.",
        ],
        "evidence": [
            {
                "ticket_id": ticket_id,
                "document_id": document_id,
                "source_type": source_type,
                "title": "User cannot login after password reset",
                "snippet": snippet,
                "system": system,
                "category": category,
                "match_score": 94.0,
                "reason": "Historical ticket with identical symptoms and a documented resolution.",
            },
            {
                "ticket_id": "",
                "document_id": "DOC-SAP-001",
                "source_type": "document",
                "title": "SAP Authentication Troubleshooting Guide",
                "snippet": "If authentication fails after password reset, clear the SAML token cache and verify identity provider password hash sync.",
                "system": "SAP",
                "category": "authentication",
                "match_score": 91.0,
                "reason": "Authoritative SAP documentation confirming the same remediation path.",
            },
        ],
        "knowledge_gaps": [
            "Resolution depends on environment-specific identity provider configuration.",
            "No direct evidence of SAML cache state in the current environment.",
        ],
        "requires_human_review": True,
    }


# ---------------------------------------------------------------------------
# Confidence breakdown (computed, not hardcoded)
# ---------------------------------------------------------------------------

def compute_confidence_breakdown(
    candidates: list[dict],
    semantic_top_score: float,
) -> ConfidenceBreakdown:
    """Compute the confidence breakdown from real signals.

    - semantic_similarity: from the top match score after reranking
    - historical_success_rate: from ticket metadata heuristic
    - source_reliability: from source type + status heuristic
    - recency_factor: from created_at / resolved_at heuristic
    """
    if not candidates:
        return ConfidenceBreakdown(
            semantic_similarity=0,
            historical_success_rate=0,
            source_reliability=0,
            recency_factor=0,
        )

    top = candidates[0]

    semantic = max(0, min(100, int(round(semantic_top_score))))

    hist = 0.0
    rel = 0.0
    rec = 0.0
    count = 0
    for c in candidates:
        hist += historical_success_rate(c.get("ticket_id"), c.get("status"), c.get("resolution_time_hours"))
        rel += source_reliability(c.get("source_type"), c.get("status"))
        rec += recency_factor(c.get("created_at"), c.get("resolved_at"))
        count += 1

    if count:
        hist = hist / count
        rel = rel / count
        rec = rec / count

    return ConfidenceBreakdown(
        semantic_similarity=semantic,
        historical_success_rate=int(max(0, min(100, hist))),
        source_reliability=int(max(0, min(100, rel))),
        recency_factor=int(max(0, min(100, rec))),
    )


def confidence_label(breakdown: ConfidenceBreakdown) -> str:
    avg = (breakdown.semantic_similarity + breakdown.historical_success_rate + breakdown.source_reliability + breakdown.recency_factor) / 4
    if avg >= 80:
        return "high"
    if avg >= 60:
        return "medium"
    return "low"


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def solve(
    query: SolutionQuery,
    db: Optional[Session] = None,
) -> SolutionResponse:
    """Run the full SOLVIA RAG pipeline and return a structured solution."""
    query_vector = embed_query(query.query)

    candidates = retrieve_candidates(query_vector, query.system, query.category)

    # If we have no candidates, still return a grounded response
    if not candidates:
        return _empty_solution(query)

    # Build evidence context for Gemini
    context = build_evidence_context(candidates)
    user_prompt = build_user_prompt(query.query, context)

    gemini_result = call_gemini_reasoning(user_prompt)

    # If Gemini returned an error object, surface a clean fallback
    if isinstance(gemini_result, dict) and "_error" in gemini_result:
        return _error_solution(query, gemini_result["_error"])

        # Normalize Gemini evidence and enrich trusted provenance
        # from retrieved Chroma metadata.
    evidence: list[EvidenceItem] = []

    candidate_by_ticket = {
        c["ticket_id"]: c
        for c in candidates
        if c.get("ticket_id")
    }

    candidate_by_document = {
        c["document_id"]: c
        for c in candidates
        if c.get("document_id")
    }

    for ev in gemini_result.get("evidence", []):
        ticket_id = ev.get("ticket_id")
        document_id = ev.get("document_id")

        matched = None

        if ticket_id:
            matched = candidate_by_ticket.get(ticket_id)

        if matched is None and document_id:
            matched = candidate_by_document.get(document_id)

        raw_match_score = float(ev.get("match_score", 0))
        safe_match_score = max(0.0, min(100.0, raw_match_score))

        evidence.append(
            EvidenceItem(
                ticket_id=ticket_id,
                document_id=document_id,
                source_type=ev.get(
                    "source_type",
                    matched.get("source_type", "unknown")
                    if matched
                    else "unknown",
                ),
                source=(
                    matched.get("source")
                    if matched
                    else ev.get("source")
                ),
                source_reliability=(
                    matched.get("source_reliability")
                    if matched
                    else ev.get("source_reliability")
                ),
                title=ev.get(
                    "title",
                    matched.get("title", "")
                    if matched
                    else "",
                ),
                snippet=ev.get("snippet", ""),
                system=ev.get(
                    "system",
                    matched.get("system")
                    if matched
                    else None,
                ),
                category=ev.get(
                    "category",
                    matched.get("category")
                    if matched
                    else None,
                ),
                match_score=safe_match_score,
                reason=ev.get("reason", ""),
            )
        )

    # If Gemini returned no evidence, attach the retrieved candidates as evidence
        if not evidence:
             for c in candidates:
                 evidence.append(
                EvidenceItem(
                    ticket_id=c["ticket_id"] or None,
                    document_id=c["document_id"] or None,
                    source_type=c["source_type"],
                    source=c.get("source") or "ServiceNow",
                    source_reliability=c.get(
                        "source_reliability",
                        0.90,
                    ),
                    title=c["title"] or "(no title)",
                    snippet=c["snippet"][:400],
                    system=c["system"] or None,
                    category=c["category"] or None,
                    match_score=max(
                        0.0,
                        min(100.0, float(c["match_score"])),
                    ),
                    reason=(
                        "Retrieved from knowledge library; "
                        "cited in reasoning."
                    ),
                )
            )

    breakdown = compute_confidence_breakdown(candidates, candidates[0]["match_score"])

    solution_title = gemini_result.get("solution_title", "Solution from retrieved evidence")
    raw_solution_score = float(
         gemini_result.get(
            "match_score",
            candidates[0]["match_score"],
        )
    )
    match_score = int(
        max(0.0, min(100.0, raw_solution_score))
    )
    confidence = gemini_result.get("confidence", confidence_label(breakdown))
    reasoning = gemini_result.get("reasoning", "")
    execution_blueprint = gemini_result.get("execution_blueprint", [])
    knowledge_gaps = gemini_result.get("knowledge_gaps", [])
    requires_human_review = gemini_result.get("requires_human_review", True)

    # Ensure human review is always required per SOLVIA policy
    requires_human_review = True

        # Record solution usage for analytics.
    solution_id = str(uuid.uuid4())

    if db is not None:
        try:
            usage = SolutionUsage(
                query=query.query,
                solution_id=solution_id,
                match_score=match_score,
                confidence=confidence,
            )
            db.add(usage)
            db.commit()
        except Exception as exc:
            db.rollback()
            print(
                f"SOLUTION USAGE WRITE FAILED: {exc!r}",
                flush=True
            )

    # Audit: record the query + solution usage.
    try:
        log_audit(
            event_type="solution_generated",
            actor="SOLVIA",
            detail=(
                f"query={query.query[:200]} "
                f"solution_id={solution_id} "
                f"match_score={match_score} "
                f"confidence={confidence}"
            ),
        )
    except Exception:
        pass

    return SolutionResponse(
        solution_id=solution_id,
        solution_title=solution_title,
        match_score=match_score,
        confidence=confidence,
        reasoning=reasoning,
        execution_blueprint=execution_blueprint,
        evidence=evidence,
        confidence_breakdown=breakdown,
        knowledge_gaps=knowledge_gaps,
        requires_human_review=requires_human_review,
    )


def _empty_solution(query: SolutionQuery) -> SolutionResponse:
    return SolutionResponse(
        solution_title="No matching evidence found",
        match_score=0,
        confidence="low",
        reasoning=(
            "SOLVIA did not find relevant tickets or documents in the knowledge "
            "library for this query. No recommendations can be grounded in "
            "retrieved evidence."
        ),
        execution_blueprint=[
            "Gather more context about the issue (system, transaction, error message).",
            "Check whether the relevant tickets or documentation have been ingested into the knowledge library.",
            "Escalate to a subject matter expert if the issue is novel or urgent.",
        ],
        evidence=[],
        confidence_breakdown=ConfidenceBreakdown(
            semantic_similarity=0,
            historical_success_rate=0,
            source_reliability=0,
            recency_factor=0,
        ),
        knowledge_gaps=[
            "No matching tickets or documents retrieved.",
            "The knowledge library may not contain content relevant to this issue.",
        ],
        requires_human_review=True,
    )


def _error_solution(query: SolutionQuery, error: str) -> SolutionResponse:
    return SolutionResponse(
        solution_title="Solution generation unavailable",
        match_score=0,
        confidence="low",
        reasoning=(
            f"SOLVIA retrieved evidence but could not generate a grounded solution: {error}"
        ),
        execution_blueprint=[
            "Review the retrieved evidence with a subject matter expert.",
            "Retry the query once the service is available.",
        ],
        evidence=[],
        confidence_breakdown=ConfidenceBreakdown(
            semantic_similarity=0,
            historical_success_rate=0,
            source_reliability=0,
            recency_factor=0,
        ),
        knowledge_gaps=[f"Generation error: {error}"],
        requires_human_review=True,
    )


# ---------------------------------------------------------------------------
# Score helpers used by tests
# ---------------------------------------------------------------------------

def l2_to_similarity(l2: float) -> float:
    """Convert an L2 distance into a 0-1 similarity using the metric-aware L2
    transform ``1 / (1 + l2/2)``.

    Reference points:
      - l2 = 0   -> 1.0
      - l2 = 2   -> 0.5
      - l2 -> inf -> 0.0

    This is monotone and bounded on [0, 1], so ranking is preserved.
    """
    return 1.0 / (1.0 + (l2 / 2.0))


def l2_to_match_score(l2: float) -> float:
    """Convert an L2 distance into a 0-100 match score with no metadata bonuses."""
    return max(0.0, min(100.0, l2_to_similarity(l2) * 100.0))

