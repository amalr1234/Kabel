"""
Quick smoke test for POST /search/solve style backend behavior.

Run from the backend directory:

    cd solvia/backend
    SOLVIA_DB_SQLITE=1 .venv/Scripts/python.exe test_solve.py

This prints the chosen Gemini model and the resulting solution response.
It does not print the API key.
"""
from __future__ import annotations

import os
import sys

os.environ["SOLVIA_DB_SQLITE"] = "1"
os.environ.setdefault("GEMINI_API_KEY", "")
sys.path.insert(0, ".")

from app.settings import get_settings
from app.query import solve
from app.schemas import SolutionQuery


def main() -> None:
    settings = get_settings()
    print("loaded gemini_model=", settings.gemini_model)
    print("loaded gemini_embedding_model=", settings.gemini_embedding_model)
    print("demo_mode=", settings.demo_mode)
    print("gemini_available=", settings.gemini_available)

    query = SolutionQuery(
        query=(
            "User cannot login to SAP after password reset. "
            "System shows Authentication failed even though password is correct."
        ),
        system="SAP",
        category="authentication",
        priority="high",
    )

    response = solve(query)

    print()
    print("=== POST /search/solve style response ===")
    print("solution_title=", response.solution_title)
    print("match_score=", response.match_score)
    print("confidence=", response.confidence)
    print("requires_human_review=", response.requires_human_review)
    print("evidence_count=", len(response.evidence))
    for ev in response.evidence:
        print("  evidence:", ev.ticket_id, ev.document_id, ev.source_type)
    print("confidence_breakdown=", response.confidence_breakdown.model_dump())
    print("knowledge_gaps=", response.knowledge_gaps)
    print("execution_blueprint_count=", len(response.execution_blueprint))
    print("reasoning[:320]=", response.reasoning[:320])


if __name__ == "__main__":
    main()
