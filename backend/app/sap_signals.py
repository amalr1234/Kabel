"""Extract SAP-oriented signals from free text for retrieval and metadata."""
from __future__ import annotations

import re
from dataclasses import dataclass, field

NOTE_RE = re.compile(
    r"\b(?:SAP\s*)?(?:Note|KBA)\s*#?\s*(\d{5,8})\b",
    re.IGNORECASE,
)
NOTE_BARE_RE = re.compile(r"\b(?:note|kba)[/\s:-]*(\d{6,8})\b", re.IGNORECASE)
TX_RE = re.compile(
    r"\b("
    r"ST22|ST03N|ST03|ST04|ST05|ST12|ST13|ST14|ST06|STMS|"
    r"SM21|SM37|SM50|SM51|SM66|SM12|SM13|SM36|SM59|SMQ1|SMQ2|"
    r"SU01|SU53|SU24|SU25|SUIM|PFCG|"
    r"SE11|SE16|SE16N|SE38|SE80|SE09|SE10|SE37|SE93|"
    r"SNOTE|SPAU|SPDD|RZ10|RZ11|RZ20|"
    r"DBACOCKPIT|DB02|STMS_IMPORT|"
    r"SAML2|OA2C_CONFIG"
    r")\b",
    re.IGNORECASE,
)
ERROR_RE = re.compile(
    r"\b("
    r"ORA-\d{4,6}|"
    r"SQL\d{3,5}|"
    r"CX_[A-Z0-9_]+|"
    r"DBIF_[A-Z0-9_]+|"
    r"TIME_OUT|"
    r"DUMP|"
    r"SAML[_-]?error|"
    r"HTTP\s?[45]\d\d"
    r")\b",
    re.IGNORECASE,
)
HEADING_RE = re.compile(
    r"(?m)^(#{1,6}\s+.+$|[A-Z][A-Z0-9][A-Z0-9 /_\-]{6,}$|\d+(?:\.\d+){0,3}\s+\S.+)$"
)


@dataclass
class SapSignals:
    notes: list[str] = field(default_factory=list)
    transactions: list[str] = field(default_factory=list)
    error_codes: list[str] = field(default_factory=list)

    def as_meta(self) -> dict[str, str]:
        return {
            "sap_notes": ",".join(self.notes),
            "transactions": ",".join(self.transactions),
            "error_codes": ",".join(self.error_codes),
        }

    def to_sets(self) -> tuple[set[str], set[str], set[str]]:
        return set(self.notes), set(self.transactions), set(self.error_codes)


def _unique(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        key = value.upper()
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def extract_signals(text: str) -> SapSignals:
    blob = text or ""
    notes = [m.group(1) for m in NOTE_RE.finditer(blob)]
    notes += [m.group(1) for m in NOTE_BARE_RE.finditer(blob)]
    transactions = [m.group(1) for m in TX_RE.finditer(blob)]
    errors = [m.group(1).replace(" ", "") for m in ERROR_RE.finditer(blob)]
    return SapSignals(
        notes=_unique(notes),
        transactions=_unique(transactions),
        error_codes=_unique(errors),
    )


def parse_csv_field(value: object) -> list[str]:
    if not value:
        return []
    return [part.strip().upper() for part in str(value).split(",") if part.strip()]


def merge_signal_fields(
    text: str,
    sap_notes: object = None,
    transactions: object = None,
    error_codes: object = None,
) -> SapSignals:
    """Signals found in ``text`` plus values entered explicitly as CSV fields."""
    found = extract_signals(text)
    return SapSignals(
        notes=_unique(parse_csv_field(sap_notes) + found.notes),
        transactions=_unique(parse_csv_field(transactions) + found.transactions),
        error_codes=_unique(parse_csv_field(error_codes) + found.error_codes),
    )


def signal_overlap_bonus(query: SapSignals, candidate_meta: dict) -> float:
    q_notes, q_tx, q_err = query.to_sets()
    c_notes = set(parse_csv_field(candidate_meta.get("sap_notes")))
    c_tx = set(parse_csv_field(candidate_meta.get("transactions")))
    c_err = set(parse_csv_field(candidate_meta.get("error_codes")))

    snippet = (candidate_meta.get("snippet") or candidate_meta.get("chunk_preview") or "").upper()
    if snippet:
        extracted = extract_signals(snippet)
        c_notes |= set(extracted.notes)
        c_tx |= set(extracted.transactions)
        c_err |= set(extracted.error_codes)

    bonus = 0.0
    bonus += 14.0 * min(2, len(q_notes & c_notes))
    bonus += 12.0 * min(2, len(q_tx & c_tx))
    bonus += 12.0 * min(2, len(q_err & c_err))
    return min(28.0, bonus)


def split_heading_blocks(text: str) -> list[str]:
    """Split on markdown / numbered / shouty headings, keeping the heading with the body."""
    cleaned = (text or "").strip()
    if not cleaned:
        return []
    matches = list(HEADING_RE.finditer(cleaned))
    if len(matches) < 2:
        paragraphs = [p.strip() for p in re.split(r"\n{2,}", cleaned) if p.strip()]
        return paragraphs or [cleaned]

    blocks: list[str] = []
    if matches[0].start() > 0:
        lead = cleaned[: matches[0].start()].strip()
        if lead:
            blocks.append(lead)
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(cleaned)
        block = cleaned[match.start() : end].strip()
        if block:
            blocks.append(block)
    return blocks


def pack_token_chunks(
    blocks: list[str],
    target_tokens: int = 400,
    overlap_tokens: int = 60,
) -> list[str]:
    """Pack heading/paragraph blocks into ~token-sized chunks with overlap."""
    if not blocks:
        return []
    target_chars = max(240, target_tokens * 4)
    overlap_chars = max(80, overlap_tokens * 4)
    chunks: list[str] = []
    current: list[str] = []
    current_len = 0

    def flush() -> None:
        nonlocal current, current_len
        if not current:
            return
        chunks.append("\n\n".join(current).strip())
        overlap = chunks[-1][-overlap_chars:] if chunks[-1] else ""
        current = [overlap] if overlap.strip() else []
        current_len = len(overlap)

    for block in blocks:
        block_len = len(block) + 2
        if len(block) > target_chars:
            flush()
            for i in range(0, len(block), target_chars - overlap_chars):
                piece = block[i : i + target_chars].strip()
                if piece:
                    chunks.append(piece)
            current = []
            current_len = 0
            continue
        if current_len + block_len > target_chars and current:
            flush()
        current.append(block)
        current_len += block_len

    if current:
        text = "\n\n".join(current).strip()
        if text:
            chunks.append(text)
    return chunks
