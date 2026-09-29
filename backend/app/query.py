"""
SOLVIA RAG query pipeline.

Query:
  User issue -> Gemini embedding -> ChromaDB semantic search -> retrieve top candidates
  -> rerank/filter -> Gemini reasoning -> structured solution

Grounding rules:
  - Gemini must NOT invent ticket IDs, SAP Notes, transactions, solutions,
    source documents, or technical facts.
  - If evidence is insufficient, say so.
  - If evidence conflicts, say so.
  - Every recommendation must be linked to retrieved evidence.
"""
from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.chroma import get_chroma_client
from app.embeddings import embed_text
from app.gemini import get_genai_client, settings
from app.ingest import DOCUMENT_COLLECTION, TICKET_COLLECTION
from app.models import SolutionUsage
from app.retrieve import filter_fallbacks, parse_query_results
from app.routers.audit import record_audit_event as log_audit
from app.sap_signals import extract_signals, signal_overlap_bonus
from app.schemas import (
    ConfidenceBreakdown,
    EvidenceItem,
    SolutionQuery,
    SolutionResponse,
)

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Configuration (tune these as you refine the engine)
# ---------------------------------------------------------------------------

TOP_K = 24
RERANK_TOP_N = 8
MIN_FILTERED_HITS = 4

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

def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _as_float(value) -> Optional[float]:
    """Chroma stores missing numbers as ``""``; treat those as ``None``."""
    if value in (None, ""):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _as_feedback_score(value) -> Optional[float]:
    score = _as_float(value)
    return None if score is None else clamp(score, 0.0, 1.0)


def distance_to_similarity(distance: float, metric: str = "l2") -> float:
    """Convert a ChromaDB distance into a 0-1 similarity for the given metric."""
    if metric == "cosine":
        return max(0.0, 1.0 - (distance / 2.0))
    if metric == "ip":
        return clamp(1.0 - (distance / (1.0 + abs(distance))), 0.0, 1.0)
    return l2_to_similarity(distance)


def score_candidate(
    result: dict,
    query_system: Optional[str],
    query_category: Optional[str],
    query_signals=None,
    metric: Optional[str] = None,
) -> float:
    """Convert a ChromaDB retrieval result into a 0-100 match-style score.

    Two transformations are applied:

    1. Distance -> semantic_similarity (metric-aware).
    2. Metadata bonuses for system/category, SAP signals, resolved status,
       and consultant feedback.
    """
    distance = float(result.get("distance", 0.0))
    base = clamp(distance_to_similarity(distance, metric or chromadb_metric()) * 100.0)

    bonus = 0.0
    if query_system and (result.get("system") or "").lower() == query_system.lower():
        bonus += 8.0
    if query_category and (result.get("category") or "").lower() == query_category.lower():
        bonus += 6.0

    if query_signals is not None:
        bonus += signal_overlap_bonus(query_signals, result)

    if (result.get("status") or "").lower() == "resolved":
        bonus += 4.0

    feedback = _as_feedback_score(result.get("feedback_score"))
    if feedback is not None:
        bonus += (feedback - 0.5) * 24.0

    return base + bonus


def recency_factor(created_at: Optional[str], resolved_at: Optional[str]) -> float:
    """Return a 0-100 recency score. More recent = higher.

    When a resolution date is present, prefer it as the 'last activity' signal.
    """
    last = resolved_at or created_at
    if not last:
        return 50.0
    try:
        dt = datetime.fromisoformat(last)
    except (TypeError, ValueError):
        return 50.0

    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    age_days = max(0.0, (datetime.now(timezone.utc) - dt).total_seconds() / 86400.0)
    # Linear decay: 100 today, 0 after a year.
    return max(0.0, 100.0 - (age_days / 365.0 * 100.0))


def historical_success_rate(
    status: Optional[str] = None,
    resolution_time_hours: Optional[float] = None,
    feedback_score: Optional[float] = None,
) -> float:
    """Return a 0-100 historical success score.

    Consultant feedback on prior solutions for this ticket is the primary
    signal. Ticket status / resolution time remain a fallback heuristic.
    """
    if feedback_score is not None:
        return clamp(feedback_score * 100.0)

    base = 70.0
    if status and status.lower() == "resolved":
        base += 10.0
    if resolution_time_hours is not None:
        if resolution_time_hours <= 2.0:
            base += 10.0
        elif resolution_time_hours <= 8.0:
            base += 5.0
    return clamp(base)


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
    """Embed a query string (deterministic placeholder vectors in demo mode)."""
    return embed_text(text)


# ---------------------------------------------------------------------------
# Semantic retrieval
# ---------------------------------------------------------------------------

_TEXT_META_KEYS = (
    "ticket_id",
    "document_id",
    "system",
    "category",
    "priority",
    "status",
    "resolver",
    "created_at",
    "resolved_at",
    "sap_notes",
    "transactions",
    "error_codes",
)


def _normalize_candidate(
    parsed: dict,
    query_system: Optional[str],
    query_category: Optional[str],
    query_signals,
    metric: str,
) -> dict:
    meta = parsed.get("metadata") or {}
    is_ticket = parsed.get("collection") == TICKET_COLLECTION
    candidate = {
        "id": parsed.get("id"),
        "collection": parsed.get("collection"),
        "source_type": meta.get("source_type") or ("ticket" if is_ticket else "document"),
        "title": meta.get("title") or "(no title)",
        "source": meta.get("source") or "ServiceNow",
        "source_reliability": meta.get("source_reliability", 0.90),
        "resolution_time_hours": _as_float(meta.get("resolution_time_hours")),
        "feedback_score": _as_feedback_score(meta.get("feedback_score")),
        "chunk_index": meta.get("chunk_index"),
        "total_chunks": meta.get("total_chunks"),
        "snippet": parsed.get("snippet") or "",
        "distance": float(parsed.get("distance") or 0.0),
        **{key: meta.get(key) or "" for key in _TEXT_META_KEYS},
    }
    candidate["match_score"] = score_candidate(
        candidate, query_system, query_category, query_signals, metric
    )
    return candidate


def _dedupe_candidates(candidates: list[dict]) -> list[dict]:
    best: dict[tuple, dict] = {}
    for candidate in candidates:
        if candidate.get("ticket_id"):
            key = ("ticket", candidate["ticket_id"])
        elif candidate.get("document_id"):
            key = ("document", candidate["document_id"])
        else:
            key = ("id", candidate.get("id"))
        current = best.get(key)
        if current is None or candidate["match_score"] > current["match_score"]:
            best[key] = candidate
    return sorted(best.values(), key=lambda item: item["match_score"], reverse=True)


def retrieve_candidates(
    query_embedding: list[float],
    query_system: Optional[str],
    query_category: Optional[str],
    query_priority: Optional[str] = None,
    query_text: Optional[str] = None,
) -> list[dict]:
    """Retrieve a wide candidate set, then rerank with SAP-aware scoring."""
    client = get_chroma_client()
    query_signals = extract_signals(query_text or "")
    metric = chromadb_metric()
    candidates: list[dict] = []
    where_variants = filter_fallbacks(
        query_system,
        query_category,
        query_priority,
        prefer_resolved=True,
    )

    for coll_name in (TICKET_COLLECTION, DOCUMENT_COLLECTION):
        try:
            coll = client.get_collection(coll_name)
        except Exception:
            continue

        collected: list[dict] = []
        for where in where_variants:
            kwargs = {
                "query_embeddings": [query_embedding],
                "n_results": TOP_K,
            }
            if where is not None:
                kwargs["where"] = where
            try:
                results = coll.query(**kwargs)
            except Exception:
                continue
            collected.extend(parse_query_results(results, coll_name))
            unique_ids = {item["id"] for item in collected}
            if len(unique_ids) >= MIN_FILTERED_HITS:
                break

        candidates.extend(
            _normalize_candidate(parsed, query_system, query_category, query_signals, metric)
            for parsed in collected
        )

    return _dedupe_candidates(candidates)[:RERANK_TOP_N]


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
        if c.get("sap_notes"):
            lines.append(f"SAP Notes: {c['sap_notes']}")
        if c.get("transactions"):
            lines.append(f"Transactions: {c['transactions']}")
        if c.get("error_codes"):
            lines.append(f"Error codes: {c['error_codes']}")
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


def call_gemini_reasoning(user_prompt: str, candidates: Optional[list[dict]] = None) -> dict:
    """Call Gemini generation with the grounding system prompt and return parsed JSON.

    In demo mode, synthesise a structured answer from retrieved candidates so the
    retrieval path can be tested without an API key.
    """
    client = get_genai_client()
    if client is None:
        if candidates:
            return _demo_solution_from_candidates(candidates)
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
    """Extract the JSON object from the Gemini response text (tolerates code fences)."""
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            parsed = json.loads(text[start : end + 1])
            if isinstance(parsed, dict):
                return parsed
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


def _demo_solution_from_candidates(candidates: list[dict]) -> dict:
    """Build a grounded demo answer from retrieved Chroma hits."""
    evidence = []
    blueprint: list[str] = []
    for candidate in candidates[:5]:
        snippet = (candidate.get("snippet") or "")[:400]
        evidence.append(
            {
                "ticket_id": candidate.get("ticket_id") or "",
                "document_id": candidate.get("document_id") or "",
                "source_type": candidate.get("source_type") or "ticket",
                "title": candidate.get("title") or "(no title)",
                "snippet": snippet,
                "system": candidate.get("system") or "",
                "category": candidate.get("category") or "",
                "match_score": float(candidate.get("match_score") or 0),
                "reason": "Retrieved from the knowledge library with SAP-aware ranking.",
            }
        )
        if "Resolution:" in snippet:
            resolution = snippet.split("Resolution:", 1)[-1].strip()
            if resolution:
                blueprint.append(resolution.split("\n")[0][:240])

    top = candidates[0]
    notes = top.get("sap_notes") or ""
    txs = top.get("transactions") or ""
    reasoning = (
        f"Ranked {len(candidates)} library hits. Top match is "
        f"{top.get('ticket_id') or top.get('document_id')} "
        f"({top.get('title')})."
    )
    if notes:
        reasoning += f" SAP Notes in evidence: {notes}."
    if txs:
        reasoning += f" Transactions in evidence: {txs}."

    return {
        "solution_title": top.get("title") or "Solution from retrieved evidence",
        "match_score": int(clamp(float(top.get("match_score") or 0))),
        "confidence": "medium",
        "reasoning": reasoning,
        "execution_blueprint": blueprint
        or ["Review the retrieved evidence with a subject matter expert."],
        "evidence": evidence,
        "knowledge_gaps": [
            "Demo mode is using retrieved evidence without Gemini generation.",
        ],
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
        return _zero_breakdown()

    def average(values) -> int:
        return int(clamp(sum(values) / len(candidates)))

    return ConfidenceBreakdown(
        semantic_similarity=int(round(clamp(semantic_top_score))),
        historical_success_rate=average(
            historical_success_rate(
                c.get("status"),
                _as_float(c.get("resolution_time_hours")),
                _as_feedback_score(c.get("feedback_score")),
            )
            for c in candidates
        ),
        source_reliability=average(
            source_reliability(c.get("source_type"), c.get("status")) for c in candidates
        ),
        recency_factor=average(
            recency_factor(c.get("created_at"), c.get("resolved_at")) for c in candidates
        ),
    )


def _zero_breakdown() -> ConfidenceBreakdown:
    return ConfidenceBreakdown(
        semantic_similarity=0,
        historical_success_rate=0,
        source_reliability=0,
        recency_factor=0,
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
    candidates = retrieve_candidates(
        embed_query(query.query),
        query.system,
        query.category,
        query.priority,
        query.query,
    )

    if not candidates:
        return _fallback_solution(
            title="No matching evidence found",
            reasoning=(
                "SOLVIA did not find relevant tickets or documents in the knowledge "
                "library for this query. No recommendations can be grounded in "
                "retrieved evidence."
            ),
            blueprint=[
                "Gather more context about the issue (system, transaction, error message).",
                "Check whether the relevant tickets or documentation have been ingested into the knowledge library.",
                "Escalate to a subject matter expert if the issue is novel or urgent.",
            ],
            gaps=[
                "No matching tickets or documents retrieved.",
                "The knowledge library may not contain content relevant to this issue.",
            ],
        )

    user_prompt = build_user_prompt(query.query, build_evidence_context(candidates))
    gemini_result = call_gemini_reasoning(user_prompt, candidates)

    if "_error" in gemini_result:
        error = gemini_result["_error"]
        return _fallback_solution(
            title="Solution generation unavailable",
            reasoning=f"SOLVIA retrieved evidence but could not generate a grounded solution: {error}",
            blueprint=[
                "Review the retrieved evidence with a subject matter expert.",
                "Retry the query once the service is available.",
            ],
            gaps=[f"Generation error: {error}"],
        )

    evidence = _build_evidence(gemini_result.get("evidence") or [], candidates)
    breakdown = compute_confidence_breakdown(candidates, candidates[0]["match_score"])
    solution_id = str(uuid.uuid4())
    solution_title = gemini_result.get("solution_title") or "Solution from retrieved evidence"
    match_score = int(clamp(float(candidates[0]["match_score"])))
    confidence = gemini_result.get("confidence") or confidence_label(breakdown)
    execution_blueprint = gemini_result.get("execution_blueprint") or []

    if db is not None:
        try:
            db.add(
                SolutionUsage(
                    query=query.query,
                    solution_id=solution_id,
                    match_score=match_score,
                    confidence=confidence,
                    solution_title=solution_title,
                    evidence_json=json.dumps([item.model_dump() for item in evidence]),
                    blueprint_json=json.dumps(execution_blueprint),
                    query_system=query.system,
                    query_category=query.category,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Solution usage write failed")

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
        logger.exception("Audit write failed")

    return SolutionResponse(
        solution_id=solution_id,
        solution_title=solution_title,
        match_score=match_score,
        confidence=confidence,
        reasoning=gemini_result.get("reasoning", ""),
        execution_blueprint=execution_blueprint,
        evidence=evidence,
        confidence_breakdown=breakdown,
        knowledge_gaps=gemini_result.get("knowledge_gaps") or [],
        requires_human_review=True,
    )


def _evidence_item(source: dict, reason: str) -> EvidenceItem:
    return EvidenceItem(
        ticket_id=source.get("ticket_id") or None,
        document_id=source.get("document_id") or None,
        source_type=source.get("source_type") or "unknown",
        source=source.get("source"),
        source_reliability=source.get("source_reliability"),
        title=source.get("title") or "(no title)",
        snippet=(source.get("snippet") or "")[:400],
        system=source.get("system") or None,
        category=source.get("category") or None,
        match_score=clamp(float(source.get("match_score") or 0)),
        reason=reason,
    )


def _build_evidence(gemini_evidence: list, candidates: list[dict]) -> list[EvidenceItem]:
    """Merge Gemini's cited evidence with the retrieved candidate it refers to.

    Provenance (source, reliability, match score) always comes from retrieval,
    never from the model.
    """
    by_ticket = {c["ticket_id"]: c for c in candidates if c["ticket_id"]}
    by_document = {c["document_id"]: c for c in candidates if c["document_id"]}

    evidence: list[EvidenceItem] = []
    for cited in gemini_evidence:
        if not isinstance(cited, dict):
            continue
        matched = by_ticket.get(cited.get("ticket_id")) or by_document.get(cited.get("document_id")) or {}
        merged = {**matched, **{k: v for k, v in cited.items() if v not in (None, "")}}
        if matched:
            for key in ("source", "source_reliability", "match_score"):
                merged[key] = matched.get(key)
        evidence.append(_evidence_item(merged, cited.get("reason", "")))

    if evidence:
        return evidence
    return [
        _evidence_item(c, "Retrieved from knowledge library; cited in reasoning.")
        for c in candidates
    ]


def _fallback_solution(
    title: str,
    reasoning: str,
    blueprint: list[str],
    gaps: list[str],
) -> SolutionResponse:
    return SolutionResponse(
        solution_id=str(uuid.uuid4()),
        solution_title=title,
        match_score=0,
        confidence="low",
        reasoning=reasoning,
        execution_blueprint=blueprint,
        evidence=[],
        confidence_breakdown=_zero_breakdown(),
        knowledge_gaps=gaps,
        requires_human_review=True,
    )


# ---------------------------------------------------------------------------
# L2 distance conversion
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
    return clamp(l2_to_similarity(l2) * 100.0)

