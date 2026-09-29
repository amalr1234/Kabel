"""Apply consultant feedback to ranked tickets and commit proven solutions."""
from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.crud import find_ticket
from app.ingest import ingest_ticket
from app.models import Feedback, SolutionUsage, Ticket
from app.query import clamp
from app.routers.audit import record_audit_event as log_audit

RATING_DELTA = {
    "helpful": 0.15,
    "not_helpful": -0.15,
    "verify_commit": 0.25,
}


def _ticket_ids_from_usage(usage: Optional[SolutionUsage]) -> list[str]:
    if usage is None or not usage.evidence_json:
        return []
    try:
        evidence = json.loads(usage.evidence_json)
    except json.JSONDecodeError:
        return []
    ids: list[str] = []
    seen: set[str] = set()
    for item in evidence:
        ticket_id = (item or {}).get("ticket_id")
        if ticket_id and ticket_id not in seen:
            seen.add(ticket_id)
            ids.append(ticket_id)
    return ids


def apply_ticket_feedback(db: Session, ticket_ids: list[str], rating: str) -> list[str]:
    delta = RATING_DELTA.get(rating, 0.0)
    updated: list[str] = []
    for ticket_id in ticket_ids:
        ticket = find_ticket(db, ticket_id)
        if ticket is None:
            continue
        current = ticket.feedback_score if ticket.feedback_score is not None else 0.5
        ticket.feedback_score = clamp(float(current) + delta, 0.0, 1.0)
        ingest_ticket(ticket, db)
        updated.append(ticket_id)
    return updated


def commit_verified_solution(
    db: Session,
    usage: Optional[SolutionUsage],
    notes: Optional[str],
) -> Optional[str]:
    if usage is None:
        return None

    try:
        blueprint = json.loads(usage.blueprint_json) if usage.blueprint_json else []
    except json.JSONDecodeError:
        blueprint = []
    if not isinstance(blueprint, list):
        blueprint = []

    resolution_lines = [str(step) for step in blueprint if str(step).strip()]
    if notes:
        resolution_lines.append(f"Consultant notes: {notes}")
    resolution = "\n".join(resolution_lines) or (notes or "Verified by consultant.")

    ticket_id = f"T-COMMIT-{uuid.uuid4().hex[:8].upper()}"
    ticket = Ticket(
        ticket_id=ticket_id,
        title=(usage.solution_title or usage.query or "Verified SOLVIA solution")[:240],
        description=usage.query or "",
        category=usage.query_category,
        system=usage.query_system,
        priority="medium",
        status="resolved",
        resolution=resolution,
        resolver="consultant",
        resolved_at=datetime.now(timezone.utc),
        resolution_time_hours=0.0,
        feedback_score=0.85,
        source="SOLVIA verify_commit",
        source_reliability=0.95,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ingest_ticket(ticket, db)
    return ticket_id


def record_solution_feedback(
    db: Session,
    solution_id: str,
    rating: str,
    notes: Optional[str],
) -> Feedback:
    usage = (
        db.query(SolutionUsage)
        .filter(SolutionUsage.solution_id == solution_id)
        .order_by(SolutionUsage.id.desc())
        .first()
    )
    ticket_ids = _ticket_ids_from_usage(usage)
    updated = apply_ticket_feedback(db, ticket_ids, rating)

    committed_ticket_id = None
    if rating == "verify_commit":
        committed_ticket_id = commit_verified_solution(db, usage, notes)

    if usage is not None:
        usage.feedback_rating = rating
        db.add(usage)

    feedback = Feedback(
        solution_id=solution_id,
        rating=rating,
        notes=notes,
        committed_ticket_id=committed_ticket_id,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)

    try:
        log_audit(
            event_type="feedback_recorded",
            actor="consultant",
            detail=(
                f"solution_id={solution_id} rating={rating} "
                f"tickets={','.join(updated) or 'none'} "
                f"committed={committed_ticket_id or ''}"
            ),
        )
    except Exception:
        pass

    return feedback
