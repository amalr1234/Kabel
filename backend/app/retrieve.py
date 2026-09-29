"""Chroma where-clauses and candidate parsing for SAP-aware retrieval."""
from __future__ import annotations

from typing import Any, Optional


def build_where(
    system: Optional[str] = None,
    category: Optional[str] = None,
    priority: Optional[str] = None,
    status: Optional[str] = None,
) -> Optional[dict[str, Any]]:
    clauses: list[dict[str, Any]] = []
    if system:
        clauses.append({"system": {"$eq": system}})
    if category:
        clauses.append({"category": {"$eq": category}})
    if priority:
        clauses.append({"priority": {"$eq": priority}})
    if status:
        clauses.append({"status": {"$eq": status}})
    if not clauses:
        return None
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


def filter_fallbacks(
    system: Optional[str],
    category: Optional[str],
    priority: Optional[str],
    *,
    prefer_resolved: bool,
) -> list[Optional[dict[str, Any]]]:
    """Progressively relax filters so an empty index slice does not hide weaker matches."""
    seen: list[str] = []
    variants: list[Optional[dict[str, Any]]] = []

    def add(where: Optional[dict[str, Any]]) -> None:
        key = repr(where)
        if key not in seen:
            seen.append(key)
            variants.append(where)

    if prefer_resolved:
        add(build_where(system, category, priority, "resolved"))
    add(build_where(system, category, priority))
    add(build_where(system, category))
    add(build_where(system))
    add(build_where(category=category) if category else None)
    add(None)
    return variants


def parse_query_results(results: dict, collection_name: str) -> list[dict]:
    if not results or not results.get("ids") or not results["ids"][0]:
        return []

    ids = results["ids"][0]
    metadatas = (results.get("metadatas") or [[]])[0]
    documents = (results.get("documents") or [[]])[0]
    distances = (results.get("distances") or [[]])[0]
    parsed: list[dict] = []

    for idx, rid in enumerate(ids):
        meta_raw = metadatas[idx] if metadatas and idx < len(metadatas) else {}
        doc_text = documents[idx] if documents and idx < len(documents) else ""
        dist = float(distances[idx]) if distances and idx < len(distances) else 0.0
        parsed.append(
            {
                "id": rid,
                "distance": dist,
                "snippet": doc_text,
                "collection": collection_name,
                "metadata": meta_raw or {},
            }
        )
    return parsed
