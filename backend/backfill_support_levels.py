"""Classify and re-embed tickets that are missing support_level."""
from __future__ import annotations

from app.database import SessionLocal, ensure_schema
from app.ingest import ingest_ticket
from app.models import Ticket
from app.support_level import apply_support_level


def main() -> None:
    ensure_schema()
    with SessionLocal() as db:
        tickets = db.query(Ticket).order_by(Ticket.id.asc()).all()
        if not tickets:
            print("No tickets found.")
            return

        for ticket in tickets:
            level, reason = apply_support_level(ticket, force=not bool(ticket.support_level))
            db.add(ticket)
            db.commit()
            db.refresh(ticket)
            result = ingest_ticket(ticket, db)
            print(
                f"{ticket.ticket_id}: {level} · chunks={result.get('chunk_count', 0)} · {reason}"
            )

    print("Support level backfill complete.")


if __name__ == "__main__":
    main()
