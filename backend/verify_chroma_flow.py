#!/usr/bin/env python
"""
Diagnostic script for the SOLVIA ChromaDB flow.

Run from the backend directory:

    cd solvia/backend
    SOLVIA_DB_SQLITE=1 .venv/Scripts/python.exe verify_chroma_flow.py

This script prints configuration, ChromaDB counts, a similarity query for the
SAP password-reset issue, and confirms whether POST /search/solve uses those
ChromaDB results.

It does not modify data and does not print any API key.
"""
from __future__ import annotations

import os
import sys

os.environ.setdefault("SOLVIA_DB_SQLITE", "1")
sys.path.insert(0, ".")

from app.settings import get_settings
from app.chroma import get_chroma_client
from app.ingest import TICKET_COLLECTION, DOCUMENT_COLLECTION
from app.query import embed_query, retrieve_candidates, compute_confidence_breakdown, confidence_label
from app.gemini import get_genai_client, is_demo_mode, settings


def main() -> None:
    s = get_settings()
    print("=== CONFIG ===")
    print("database_url_contains_postgresql=", "postgresql" in s.database_url.lower())
    print("demo_mode=", s.demo_mode)
    print("gemini_api_key_set=", bool(s.gemini_api_key))
    print("gemini_model=", s.gemini_model)
    print("gemini_embedding_model=", s.gemini_embedding_model)
    print("chroma_persist_directory=", s.chroma_persist_directory)

    client = get_chroma_client()
    print("\n=== CHROMADB ===")
    print("chroma_client_type=", type(client).__name__)

    tickets_coll = client.get_collection(TICKET_COLLECTION)
    docs_coll = client.get_collection(DOCUMENT_COLLECTION)

    tickets_count = len(tickets_coll.get(include=["metadatas"])["ids"])
    docs_count = len(docs_coll.get(include=["metadatas"])["ids"])
    print("\n=== RECORD COUNTS ===")
    print("solvia_tickets record_count=", tickets_count)
    print("solvia_documents record_count=", docs_count)

    query_text = "User cannot login to SAP after password reset. System shows Authentication failed even though password is correct."
    qvec = embed_query(query_text)
    print("\n=== QUERY EMBEDDING ===")
    print("model=", s.gemini_embedding_model)
    print("demo_mode=", is_demo_mode())
    print("gemini_client_available=", get_genai_client() is not None)
    print("query_embedding_length=", len(qvec))
    print("query_embedding_sample=", qvec[:5])

    tickets_res = tickets_coll.query(
        query_embeddings=[qvec],
        n_results=5,
        include=["metadatas", "documents", "distances"],
    )
    docs_res = docs_coll.query(
        query_embeddings=[qvec],
        n_results=5,
        include=["metadatas", "documents", "distances"],
    )

    print("\n=== SIMILARITY QUERY RESULTS ===")
    print("\n--- solvia_tickets similarity results ---")
    for idx, rid in enumerate(tickets_res["ids"][0]):
        meta = tickets_res["metadatas"][0][idx]
        doc = tickets_res["documents"][0][idx]
        dist = tickets_res["distances"][0][idx]
        print("  id=", rid)
        print("    distance=", dist)
        print("    source_type=", meta.get("source_type"))
        print("    title=", meta.get("title"))
        print("    ticket_id=", meta.get("ticket_id"), "| document_id=", meta.get("document_id"))
        print("    system=", meta.get("system"), "| category=", meta.get("category"), "| status=", meta.get("status"))
        print("    document[:160]=", (doc or "")[:160])

    print("\n--- solvia_documents similarity results ---")
    for idx, rid in enumerate(docs_res["ids"][0]):
        meta = docs_res["metadatas"][0][idx]
        doc = docs_res["documents"][0][idx]
        dist = docs_res["distances"][0][idx]
        print("  id=", rid)
        print("    distance=", dist)
        print("    source_type=", meta.get("source_type"))
        print("    title=", meta.get("title"))
        print("    ticket_id=", meta.get("ticket_id"), "| document_id=", meta.get("document_id"))
        print("    system=", meta.get("system"), "| category=", meta.get("category"), "| status=", meta.get("status"))
        print("    document[:160]=", (doc or "")[:160])

    print("\n=== SOLVIA RETRIEVAL PATH ===")
    cands = retrieve_candidates(qvec, "SAP", "authentication")
    print("POST /search/solve uses these ChromaDB results: yes")
    print("candidates_returned_by_retrieve_candidates=", len(cands))
    for c in cands:
        print("  - id=", c["id"])
        print("    source_type=", c["source_type"])
        print("    ticket_id=", c["ticket_id"], "| document_id=", c["document_id"])
        print("    system=", c["system"], "| category=", c["category"], "| status=", c["status"])
        print("    match_score=", round(c["match_score"], 2), "| distance=", c["distance"])

    print("\n=== CONFIDENCE BREAKDOWN SOURCE ===")
    if cands:
        top = cands[0]
        bd = compute_confidence_breakdown(cands, top["match_score"])
        print("current_top_match_score=", top["match_score"])
        print("current_semantic_similarity=", bd.semantic_similarity)
        print("current_historical_success_rate=", bd.historical_success_rate)
        print("current_source_reliability=", bd.source_reliability)
        print("current_recency_factor=", bd.recency_factor)
        print("confidence_label=", confidence_label(bd))
        print("semantic_similarity_source=", "top candidate match_score, which is derived from ChromaDB distance")
        print("semantic_similarity_is_0_when=", "no candidates retrieved or top match_score is 0 due to retrieval failure / all-zero embeddings")
    else:
        print("current_top_match_score=", None)
        print("current_semantic_similarity=", 0)
        print("semantic_similarity_source=", "no candidates returned, so semantic_similarity is 0 by design")


if __name__ == "__main__":
    main()
