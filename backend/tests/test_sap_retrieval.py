import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieve import build_where, filter_fallbacks
from app.sap_signals import extract_signals, merge_signal_fields, signal_overlap_bonus
from app.query import _parse_gemini_json, score_candidate, l2_to_match_score


def test_extract_sap_note_and_transaction():
    signals = extract_signals("Dump in ST22 after SNOTE. SAP Note 1234567. SU53 missing auth.")
    assert "1234567" in signals.notes
    assert "ST22" in signals.transactions
    assert "SU53" in signals.transactions


def test_signal_overlap_bonus_boosts_matching_note():
    query = extract_signals("ST22 dump SAP Note 1234567")
    bonus = signal_overlap_bonus(
        query,
        {"sap_notes": "1234567", "transactions": "ST22", "error_codes": "", "snippet": ""},
    )
    none = signal_overlap_bonus(
        query,
        {"sap_notes": "", "transactions": "", "error_codes": "", "snippet": "printer jam"},
    )
    assert bonus > none
    assert bonus >= 20


def test_chroma_where_and_filter_fallbacks():
    where = build_where("SAP", "authorization", None, "resolved")
    assert where == {
        "$and": [
            {"system": {"$eq": "SAP"}},
            {"category": {"$eq": "authorization"}},
            {"status": {"$eq": "resolved"}},
        ]
    }
    variants = filter_fallbacks("SAP", "authorization", None, prefer_resolved=True)
    assert variants[0]["$and"][-1] == {"status": {"$eq": "resolved"}}
    assert variants[-1] is None


def test_feedback_score_changes_rank():
    base = {"distance": 2.0, "system": "SAP", "category": "authorization", "status": "resolved"}
    low = score_candidate({**base, "feedback_score": 0.1}, "SAP", "authorization")
    high = score_candidate({**base, "feedback_score": 0.9}, "SAP", "authorization")
    assert high > low
    assert high > l2_to_match_score(2.0)


def test_manual_sap_fields_are_kept_alongside_text_signals():
    signals = merge_signal_fields("Dump in ST22, see SAP Note 7654321", "1234567", "stms", "")
    assert signals.notes == ["1234567", "7654321"]
    assert signals.transactions == ["STMS", "ST22"]


def test_parse_gemini_json_handles_code_fences():
    parsed = _parse_gemini_json('```json\n{"solution_title": "Fix", "evidence": [{"a": 1}]}\n```')
    assert parsed["solution_title"] == "Fix"
    assert parsed["evidence"] == [{"a": 1}]
