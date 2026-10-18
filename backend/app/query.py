from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Optional

from flashrank import Ranker, RerankRequest
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
    GeminiSolutionOutput,
    SolutionQuery,
    SolutionResponse,
)
from app.support_level import (
    classify_support_level,
    normalize_level,
    routing_hint,
)

logger = logging.getLogger(__name__)

TOP_K = 24
RERANK_TOP_N = 8
MIN_FILTERED_HITS = 4
CHROMADB_METRICS = frozenset({"l2", "cosine", "ip"})

# Initialize lightweight local cross-encoder ranker
try:
    cross_ranker = Ranker(model_name="ms-marco-MiniLM-L-12-v2")
except Exception as e:
    logger.warning("FlashRank init failed, falling back to heuristic sorting: %s", e)
    cross_ranker = None


def chromadb_metric() -> str:
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


def clamp(value: float, low: float = 0.0, high: float = 100.0) -> float:
    return max(low, min(high, value))


def _as_float(value) -> Optional[float]:
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
    if metric == "cosine":
        return max(0.0, 1.0 - (distance / 2.0))
    if metric == "ip":
        return clamp(1.0 - (distance / (1.0 + abs(distance))), 0.0, 1.0)
    return l2_to_similarity(distance)


def l2_to_similarity(l2: float) -> float:
    return 1.0 / (1.0 + (l2 / 2.0))


def score_candidate(
    result: dict,
    query_system: Optional[str],
    query_category: Optional[str],
    query_signals=None,
    metric: Optional[str] = None,
    query_support_level: Optional[str] = None,
) -> float:
    distance = float(result.get("distance", 0.0))
    base = clamp(distance_to_similarity(distance, metric or chromadb_metric()) * 100.0)

    bonus = 0.0
    if query_system and (result.get("system") or "").lower() == query_system.lower():
        bonus += 8.0
    if query_category and (result.get("category") or "").lower() == query_category.lower():
        bonus += 6.0
    wanted = normalize_level(query_support_level)
    candidate_level = normalize_level(result.get("support_level"))
    if wanted and candidate_level:
        if wanted == candidate_level:
            bonus += 10.0
        else:
            bonus -= 4.0
    if query_signals is not None:
        bonus += signal_overlap_bonus(query_signals, result)
    if (result.get("status") or "").lower() == "resolved":
        bonus += 4.0

    feedback = _as_feedback_score(result.get("feedback_score"))
    if feedback is not None:
        bonus += (feedback - 0.5) * 24.0

    return clamp(base + bonus)


def recency_factor(created_at: Optional[str], resolved_at: Optional[str]) -> float:
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
    return max(0.0, 100.0 - (age_days / 365.0 * 100.0))


def historical_success_rate(
    status: Optional[str] = None,
    resolution_time_hours: Optional[float] = None,
    feedback_score: Optional[float] = None,
) -> float:
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
    if not source_type:
        return 50.0
    t = source_type.lower()
    if t == "ticket":
        return 90.0 if (status and status.lower() == "resolved") else 70.0
    if t in ("pdf", "documentation", "sap_note", "note", "manual"):
        return 85.0
    if t in ("csv", "json", "markdown", "txt"):
        return 75.0
    return 60.0


def embed_query(text: str) -> list[float]:
    return embed_text(text)


_TEXT_META_KEYS = (
    "ticket_id",
    "document_id",
    "system",
    "category",
    "priority",
    "support_level",
    "support_level_reason",
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
    query_support_level: Optional[str] = None,
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
        candidate,
        query_system,
        query_category,
        query_signals,
        metric,
        query_support_level,
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
    return list(best.values())


def rerank_candidates(query_text: str, candidates: list[dict], top_n: int = RERANK_TOP_N) -> list[dict]:
    if not candidates:
        return []
    deduped = _dedupe_candidates(candidates)

    if cross_ranker is None:
        return sorted(deduped, key=lambda item: item["match_score"], reverse=True)[:top_n]

    passages = [
        {"id": c["id"], "text": f"{c['title']}. {c['snippet']}", "meta": c}
        for c in deduped
    ]

    try:
        rerank_request = RerankRequest(query=query_text, passages=passages)
        results = cross_ranker.rerank(rerank_request)
        final_list = []
        for res in results[:top_n]:
            c = res["meta"]
            # Blend cross-encoder semantic score with metadata bonuses
            ce_score = clamp(float(res["score"]) * 100.0)
            c["match_score"] = round(0.7 * ce_score + 0.3 * c["match_score"], 1)
            final_list.append(c)
        return final_list
    except Exception as exc:
        logger.warning("FlashRank execution failed, falling back: %s", exc)
        return sorted(deduped, key=lambda item: item["match_score"], reverse=True)[:top_n]


def retrieve_candidates(
    query_embedding: list[float],
    query_system: Optional[str],
    query_category: Optional[str],
    query_priority: Optional[str] = None,
    query_text: Optional[str] = None,
    query_support_level: Optional[str] = None,
) -> list[dict]:
    client = get_chroma_client()
    raw_query = query_text or ""
    query_signals = extract_signals(raw_query)
    metric = chromadb_metric()
    wanted_level = normalize_level(query_support_level)
    candidates: list[dict] = []
    where_variants = filter_fallbacks(
        query_system,
        query_category,
        query_priority,
        wanted_level,
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
            _normalize_candidate(
                parsed,
                query_system,
                query_category,
                query_signals,
                metric,
                wanted_level,
            )
            for parsed in collected
        )

    return rerank_candidates(raw_query, candidates, RERANK_TOP_N)


_SYSTEM_PROMPT = """\
You are SOLVIA, an enterprise AI intelligence engine for SAP/IT support consultants.

Reason ONLY from the retrieved evidence provided below. Do NOT invent,
hallucinate, or assume any ticket IDs, SAP Notes, transactions, commands,
solutions, or technical facts.

Grounding rules:
- Every recommendation must cite the ticket_id or document_id and state why it supports the fix.
- If evidence is insufficient, identify the missing logs/parameters in knowledge_gaps.
- Output MUST strictly adhere to the defined JSON schema.
"""


def build_evidence_context(candidates: list[dict]) -> str:
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
        if c.get("support_level"):
            lines.append(f"Support level: {c['support_level']}")
        if c.get("sap_notes"):
            lines.append(f"SAP Notes: {c['sap_notes']}")
        if c.get("transactions"):
            lines.append(f"Transactions: {c['transactions']}")
        if c.get("error_codes"):
            lines.append(f"Error codes: {c['error_codes']}")
        lines.append(f"Match score: {c['match_score']:.1f}")
        lines.append(f"Content snippet: {c['snippet']}\n")
    return "\n".join(lines)


def call_gemini_reasoning(user_prompt: str, candidates: Optional[list[dict]] = None) -> dict:
    client = get_genai_client()
    if client is None:
        if candidates:
            return _demo_solution_from_candidates(candidates)
        return _demo_solution(user_prompt)

    try:
        from google.genai import types

        config = types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=GeminiSolutionOutput,
            temperature=0.1,
        )

        resp = client.models.generate_content(
            model=settings.gemini_model,
            contents=[_SYSTEM_PROMPT, user_prompt],
            config=config,
        )

        if hasattr(resp, "parsed") and resp.parsed:
            return resp.parsed.model_dump()

        return json.loads(resp.text or "{}")

    except Exception as exc:
        logger.exception("Gemini structured reasoning call failed: %s", exc)
        return {"_error": str(exc)}


def _demo_solution_from_candidates(candidates: list[dict]) -> dict:
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
                "support_level": candidate.get("support_level") or "",
                "match_score": float(candidate.get("match_score") or 0),
                "reason": "Retrieved from the knowledge library with hybrid re-ranking.",
            }
        )
        if "Resolution:" in snippet:
            res = snippet.split("Resolution:", 1)[-1].strip()
            if res:
                blueprint.append(res.split("\n")[0][:240])

    top = candidates[0]
    return {
        "solution_title": top.get("title") or "Solution from retrieved evidence",
        "match_score": int(clamp(float(top.get("match_score") or 0))),
        "confidence": "medium",
        "reasoning": f"Ranked {len(candidates)} hits. Top evidence match is {top.get('ticket_id') or top.get('document_id')} ({top.get('title')}).",
        "execution_blueprint": blueprint or ["Review the retrieved evidence with a subject matter expert."],
        "evidence": evidence,
        "knowledge_gaps": ["Running in demo mode: verify system configuration against latest enterprise runbooks."],
        "requires_human_review": True,
    }


def _demo_solution(user_prompt: str) -> dict:
    return {
        "solution_title": "Authentication failure after password reset",
        "match_score": 92,
        "confidence": "high",
        "reasoning": "Historical records indicate a stale SAML token cache or synchronization delay following credentials updates.",
        "execution_blueprint": [
            "Clear SAML token cache.",
            "Verify identity provider hash sync.",
            "Confirm role assignments and re-test.",
        ],
        "evidence": [],
        "knowledge_gaps": ["No live SAML trace attached in query."],
        "requires_human_review": True,
    }


def compute_confidence_breakdown(candidates: list[dict], top_score: float) -> ConfidenceBreakdown:
    if not candidates:
        return ConfidenceBreakdown(semantic_similarity=0, historical_success_rate=0, source_reliability=0, recency_factor=0)

    def average(values) -> int:
        return int(clamp(sum(values) / len(candidates)))

    return ConfidenceBreakdown(
        semantic_similarity=int(round(clamp(top_score))),
        historical_success_rate=average(
            historical_success_rate(c.get("status"), _as_float(c.get("resolution_time_hours")), _as_feedback_score(c.get("feedback_score")))
            for c in candidates
        ),
        source_reliability=average(source_reliability(c.get("source_type"), c.get("status")) for c in candidates),
        recency_factor=average(recency_factor(c.get("created_at"), c.get("resolved_at")) for c in candidates),
    )


def _suggest_support_level(
    query: SolutionQuery,
    candidates: list[dict],
    gemini_result: Optional[dict] = None,
) -> tuple[Optional[str], Optional[str], Optional[str]]:
    """Prefer consultant filter, then Gemini, then rules, then top evidence."""
    filtered = normalize_level(query.support_level)
    if filtered:
        reason = f"Consultant filtered search to {filtered}."
        return filtered, reason, routing_hint(filtered)

    gemini_level = normalize_level((gemini_result or {}).get("support_level"))
    gemini_reason = (gemini_result or {}).get("support_level_reason")
    if gemini_level:
        reason = gemini_reason or f"Model suggested {gemini_level} from retrieved evidence."
        return gemini_level, reason, routing_hint(gemini_level)

    rule_level, rule_reason = classify_support_level(
        title="",
        description=query.query,
        category=query.category,
        system=query.system,
    )
    top_levels = [
        normalize_level(c.get("support_level"))
        for c in candidates[:5]
        if normalize_level(c.get("support_level"))
    ]
    if top_levels:
        # Majority vote among top evidence; ties keep rule-based level.
        counts: dict[str, int] = {}
        for level in top_levels:
            counts[level] = counts.get(level, 0) + 1
        majority = max(counts, key=lambda key: (counts[key], {"L3": 3, "L2": 2, "L1": 1}[key]))
        if counts[majority] >= 2 or majority == rule_level:
            reason = candidates[0].get("support_level_reason") or (
                f"Top evidence majority is {majority} ({counts[majority]}/{len(top_levels)})."
            )
            return majority, reason, routing_hint(majority)

    return rule_level, rule_reason, routing_hint(rule_level)


def solve(query: SolutionQuery, db: Optional[Session] = None) -> SolutionResponse:
    wanted_level = normalize_level(query.support_level)
    candidates = retrieve_candidates(
        embed_query(query.query),
        query.system,
        query.category,
        query.priority,
        query.query,
        wanted_level,
    )

    if not candidates:
        level, reason, route = _suggest_support_level(query, [], None)
        return SolutionResponse(
            solution_id=str(uuid.uuid4()),
            solution_title="No matching evidence found",
            match_score=0,
            confidence="low",
            reasoning="SOLVIA did not find relevant tickets or runbooks matching this incident.",
            execution_blueprint=["Gather exact error messages or transaction codes.", "Escalate to SME."],
            evidence=[],
            confidence_breakdown=ConfidenceBreakdown(semantic_similarity=0, historical_success_rate=0, source_reliability=0, recency_factor=0),
            knowledge_gaps=["No historical records found for this symptom description."],
            requires_human_review=True,
            support_level=level,
            support_level_reason=reason,
            support_level_routing=route,
        )

    context = build_evidence_context(candidates)
    user_prompt = (
        f"User issue:\n{query.query}\n\n"
        f"Consultant filters: system={query.system or 'any'}, "
        f"category={query.category or 'any'}, priority={query.priority or 'any'}, "
        f"support_level={wanted_level or 'any'}\n\n"
        f"Also classify the issue as L1, L2, or L3 support ownership in support_level "
        f"and explain briefly in support_level_reason.\n\n"
        f"Retrieved evidence:\n{context}"
    )
    gemini_result = call_gemini_reasoning(user_prompt, candidates)

    evidence = _build_evidence(gemini_result.get("evidence") or [], candidates)
    breakdown = compute_confidence_breakdown(candidates, candidates[0]["match_score"])
    solution_id = str(uuid.uuid4())
    solution_title = gemini_result.get("solution_title") or "Grounded Solution"
    match_score = int(clamp(float(candidates[0]["match_score"])))
    confidence = gemini_result.get("confidence") or "medium"
    execution_blueprint = gemini_result.get("execution_blueprint") or []
    knowledge_gaps = gemini_result.get("knowledge_gaps") or []
    support_level, support_reason, support_route = _suggest_support_level(
        query, candidates, gemini_result
    )

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
                    gaps_json=json.dumps(knowledge_gaps),
                    gap_count=len(knowledge_gaps),
                    query_system=query.system,
                    query_category=query.category,
                    query_support_level=wanted_level,
                    suggested_support_level=support_level,
                )
            )
            db.commit()
        except Exception:
            db.rollback()
            logger.exception("Failed to write solution usage")

    try:
        log_audit(
            event_type="solution_generated",
            actor="SOLVIA",
            detail=(
                f"query={query.query[:100]} solution_id={solution_id} "
                f"score={match_score} gaps={len(knowledge_gaps)} level={support_level}"
            ),
        )
    except Exception:
        pass

    return SolutionResponse(
        solution_id=solution_id,
        solution_title=solution_title,
        match_score=match_score,
        confidence=confidence,
        reasoning=gemini_result.get("reasoning", ""),
        execution_blueprint=execution_blueprint,
        evidence=evidence,
        confidence_breakdown=breakdown,
        knowledge_gaps=knowledge_gaps,
        requires_human_review=True,
        support_level=support_level,
        support_level_reason=support_reason,
        support_level_routing=support_route,
    )


def _build_evidence(gemini_evidence: list, candidates: list[dict]) -> list[EvidenceItem]:
    by_ticket = {c["ticket_id"]: c for c in candidates if c["ticket_id"]}
    by_document = {c["document_id"]: c for c in candidates if c["document_id"]}

    evidence: list[EvidenceItem] = []
    for cited in gemini_evidence:
        if not isinstance(cited, dict):
            continue
        matched = by_ticket.get(cited.get("ticket_id")) or by_document.get(cited.get("document_id")) or {}
        merged = {**matched, **{k: v for k, v in cited.items() if v not in (None, "")}}
        evidence.append(
            EvidenceItem(
                ticket_id=merged.get("ticket_id"),
                document_id=merged.get("document_id"),
                source_type=merged.get("source_type") or "ticket",
                source=matched.get("source") or merged.get("source"),
                source_reliability=matched.get("source_reliability"),
                title=merged.get("title") or "(no title)",
                snippet=(merged.get("snippet") or "")[:400],
                system=merged.get("system"),
                category=merged.get("category"),
                support_level=merged.get("support_level") or None,
                match_score=clamp(float(matched.get("match_score") or merged.get("match_score") or 0)),
                reason=cited.get("reason", "Cited in grounded synthesis"),
            )
        )

    if evidence:
        return evidence
    return [
        EvidenceItem(
            ticket_id=c.get("ticket_id"),
            document_id=c.get("document_id"),
            source_type=c.get("source_type") or "ticket",
            source=c.get("source"),
            source_reliability=c.get("source_reliability"),
            title=c.get("title") or "(no title)",
            snippet=(c.get("snippet") or "")[:400],
            system=c.get("system"),
            category=c.get("category"),
            support_level=c.get("support_level") or None,
            match_score=clamp(float(c.get("match_score") or 0)),
            reason="Retrieved candidate supporting recommendation",
        )
        for c in candidates
    ]