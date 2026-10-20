"""Rule-based support tier classification (L1 / L2 / L3).

Priority (low/medium/high/critical) is urgency.
Support level is who should own the work and how complex the fix is.
"""
from __future__ import annotations

from typing import Literal, Optional

SupportLevel = Literal["L1", "L2", "L3"]

LEVEL_LABELS: dict[SupportLevel, str] = {
    "L1": "Service desk / known procedure",
    "L2": "Application / functional support",
    "L3": "Basis / expert / deep investigation",
}

LEVEL_ROUTING: dict[SupportLevel, str] = {
    "L1": "Route to L1 service desk. Follow the known runbook; escalate only if the standard steps fail.",
    "L2": "Route to L2 application support. Expect log review, role/config checks, or integration credentials.",
    "L3": "Route to L3 Basis/expert. Expect deep diagnosis, system change, or SAP Note implementation.",
}

_L1_CATEGORIES = {"authentication", "password", "unlock", "access_request"}
_L3_CATEGORIES = {"performance", "installation", "upgrade", "basis", "kernel", "database"}
_L2_CATEGORIES = {"authorization", "backup", "transport", "integration", "cpi"}

_L1_TRANSACTIONS = {"su01", "su10", "suim"}
_L2_TRANSACTIONS = {"su53", "st22", "sm37", "sm21", "stms", "pfcg"}
_L3_TRANSACTIONS = {"st03n", "st04", "dbacockpit", "rz10", "rz11", "snote", "sum", "swpm"}

_L1_PHRASES = (
    "password reset",
    "unlock user",
    "user locked",
    "forgot password",
    "reset password",
    "account locked",
    "cannot login",
    "login failed",
)
_L3_PHRASES = (
    "memory dump",
    "out of memory",
    "kernel",
    "upgrade stopped",
    "installation failed",
    "sum phase",
    "transport directory",
    "work process",
    "expensive sql",
)


def normalize_level(value: Optional[str]) -> Optional[SupportLevel]:
    if not value:
        return None
    raw = value.strip().upper()
    if raw in ("L1", "L2", "L3"):
        return raw  # type: ignore[return-value]
    return None


def classify_support_level(
    *,
    title: str = "",
    description: str = "",
    resolution: str = "",
    category: Optional[str] = None,
    system: Optional[str] = None,
    transactions: Optional[str] = None,
    sap_notes: Optional[str] = None,
    error_codes: Optional[str] = None,
    resolution_time_hours: Optional[float] = None,
) -> tuple[SupportLevel, str]:
    """Return (level, short reason) using deterministic rules."""
    text = " ".join(
        part for part in (title, description, resolution, error_codes or "") if part
    ).lower()
    cat = (category or "").strip().lower()
    txn_tokens = {
        token.strip().lower()
        for token in (transactions or "").replace(";", ",").split(",")
        if token.strip()
    }
    has_sap_note = bool((sap_notes or "").strip())
    hours = resolution_time_hours

    l1_hits: list[str] = []
    l2_hits: list[str] = []
    l3_hits: list[str] = []

    if cat in _L1_CATEGORIES:
        l1_hits.append(f"category={cat}")
    if cat in _L2_CATEGORIES:
        l2_hits.append(f"category={cat}")
    if cat in _L3_CATEGORIES:
        l3_hits.append(f"category={cat}")

    for phrase in _L1_PHRASES:
        if phrase in text:
            l1_hits.append(f"phrase={phrase}")
            break
    for phrase in _L3_PHRASES:
        if phrase in text:
            l3_hits.append(f"phrase={phrase}")
            break

    if txn_tokens & _L1_TRANSACTIONS:
        l1_hits.append(f"txn={','.join(sorted(txn_tokens & _L1_TRANSACTIONS))}")
    if txn_tokens & _L2_TRANSACTIONS:
        l2_hits.append(f"txn={','.join(sorted(txn_tokens & _L2_TRANSACTIONS))}")
    if txn_tokens & _L3_TRANSACTIONS:
        l3_hits.append(f"txn={','.join(sorted(txn_tokens & _L3_TRANSACTIONS))}")

    if has_sap_note:
        # Notes often mean config/kernel guidance → at least L2, often L3 when paired with deep cats.
        if cat in _L3_CATEGORIES or hours is not None and hours >= 6.0:
            l3_hits.append("sap_note+deep_signal")
        else:
            l2_hits.append("sap_note")

    if hours is not None:
        if hours <= 1.5:
            l1_hits.append(f"resolution_time={hours}h")
        elif hours >= 8.0:
            l3_hits.append(f"resolution_time={hours}h")
        elif hours >= 3.0:
            l2_hits.append(f"resolution_time={hours}h")

    if "custom report" in text or "custom abap" in text or "z-program" in text:
        l3_hits.append("custom_code")

    scores = {
        "L1": len(l1_hits),
        "L2": len(l2_hits) + (1 if not (l1_hits or l3_hits) else 0),
        "L3": len(l3_hits),
    }

    # Prefer the strongest non-zero signal; ties break toward deeper ownership.
    ordered: list[SupportLevel] = ["L3", "L2", "L1"]
    best = max(ordered, key=lambda level: (scores[level], ordered.index(level) * -1))

    if scores[best] == 0:
        return "L2", "No strong L1/L3 signals; defaulting to L2 application support."

    reason_bits = {
        "L1": l1_hits,
        "L2": l2_hits or ["balanced application-support signals"],
        "L3": l3_hits,
    }[best]
    reason = f"{best}: " + "; ".join(reason_bits[:4])
    if system:
        reason += f" (system={system})"
    return best, reason


def classify_ticket_fields(ticket) -> tuple[SupportLevel, str]:
    return classify_support_level(
        title=getattr(ticket, "title", "") or "",
        description=getattr(ticket, "description", "") or "",
        resolution=getattr(ticket, "resolution", "") or "",
        category=getattr(ticket, "category", None),
        system=getattr(ticket, "system", None),
        transactions=getattr(ticket, "transactions", None),
        sap_notes=getattr(ticket, "sap_notes", None),
        error_codes=getattr(ticket, "error_codes", None),
        resolution_time_hours=getattr(ticket, "resolution_time_hours", None),
    )


def apply_support_level(ticket, *, force: bool = False) -> tuple[SupportLevel, str]:
    """Persist level on a ticket model when missing (or always if force=True)."""
    existing = normalize_level(getattr(ticket, "support_level", None))
    if existing and not force:
        reason = getattr(ticket, "support_level_reason", None) or LEVEL_LABELS[existing]
        return existing, reason

    level, reason = classify_ticket_fields(ticket)
    ticket.support_level = level
    ticket.support_level_reason = reason
    return level, reason


def routing_hint(level: Optional[str]) -> Optional[str]:
    normalized = normalize_level(level)
    if not normalized:
        return None
    return LEVEL_ROUTING[normalized]
