"""
Tests for the ChromaDB distance -> match_score conversion.

These tests do not hardcode scores and they do not touch the frontend or the
ChromaDB collection. They exercise the same scoring helpers used by
``retrieve_candidates`` and verify monotonicity, bounds, and separation.
"""
from __future__ import annotations

import math
import sys
import os

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.query import (
    l2_to_similarity,
    l2_to_match_score,
    score_candidate,
    chromadb_metric,
)


def approx(a: float, b: float, tol: float = 1e-9) -> None:
    assert abs(a - b) <= tol, f"{a} != {b} (tol={tol})"


def test_metric_is_l2_in_current_project() -> None:
    metric = chromadb_metric()
    assert metric in {"l2", "cosine", "ip"}, f"Unexpected metric: {metric}"
    assert metric == "l2", f"Expected l2 in this project, got {metric}"


def test_l2_to_similarity_is_monotone() -> None:
    a, b, c = 100.0, 200.0, 400.0
    sa = l2_to_similarity(a)
    sb = l2_to_similarity(b)
    sc = l2_to_similarity(c)
    assert sa > sb > sc
    assert 0.0 <= sa <= 1.0
    assert 0.0 <= sb <= 1.0
    assert 0.0 <= sc <= 1.0


def test_l2_to_similarity_reference_points() -> None:
    approx(l2_to_similarity(0.0), 1.0)
    approx(l2_to_similarity(2.0), 0.5)
    assert 0.0 < l2_to_similarity(1e9) < 1.0


def test_l2_to_match_score_reference_points() -> None:
    approx(l2_to_match_score(0.0), 100.0)
    approx(l2_to_match_score(2.0), 50.0)
    assert 0.0 <= l2_to_match_score(100.0) <= 100.0
    assert 0.0 <= l2_to_match_score(400.0) <= 100.0
    assert 0.0 <= l2_to_match_score(10000.0) <= 100.0


def test_l2_to_match_score_is_monotone() -> None:
    a, b = 200.0, 400.0
    assert l2_to_match_score(a) > l2_to_match_score(b)


def test_score_candidate_matchesDistanceFormula() -> None:
    for l2 in (10.0, 100.0, 200.0, 400.0, 700.0):
        raw = l2_to_match_score(l2)
        scored = score_candidate({"distance": l2, "sys": "", "cat": ""}, None, None)
        assert scored == raw, f"l2={l2}: score_candidate={scored}, expected={raw}"


def test_score_candidate_adds_metadata_bonus() -> None:
    base_l2 = 200.0
    base = l2_to_match_score(base_l2)

    with_sys = score_candidate({"distance": base_l2, "sys": "SAP", "cat": ""}, "SAP", None)
    assert with_sys > base

    with_cat = score_candidate({"distance": base_l2, "sys": "", "cat": "authentication"}, None, "authentication")
    assert with_cat > base

    with_both = score_candidate({"distance": base_l2, "sys": "SAP", "cat": "authentication"}, "SAP", "authentication")
    assert with_both > with_sys
    assert with_both > with_cat


def test_score_candidate_does_not_overinflate_smallDistances() -> None:
    small_l2 = 0.0001
    assert l2_to_match_score(small_l2) >= 50.0
    assert l2_to_match_score(small_l2) < 100.0


def test_l2_to_match_score_small_distances_are_high_not_perfect() -> None:
    approx(l2_to_match_score(0.0), 100.0)
    assert l2_to_match_score(0.0001) < l2_to_match_score(0.0)


def test_sap_password_reset_vs_unrelated_printer() -> None:
    matched_l2 = 343.9045
    unrelated_l2 = 343.4015

    matched_score = l2_to_match_score(matched_l2)
    unrelated_score = l2_to_match_score(unrelated_l2)

    assert matched_l2 > unrelated_l2
    assert matched_score < unrelated_score


def test_matching_query_gets_meaningful_score() -> None:
    for l2 in (1.0, 10.0, 100.0):
        score = l2_to_match_score(l2)
        assert 0.0 < score <= 100.0
        assert l2_to_match_score(l2 - 1.0) > score


def test_matching_query_score_is_bounded_above_by_perfect_match() -> None:
    approx(l2_to_match_score(0.0), 100.0)
    assert l2_to_match_score(0.001) < 100.0
    assert l2_to_match_score(100.0) < l2_to_match_score(0.0)


def test_calibration_keeps_ordering_for_current_retrieval() -> None:
    ticket_l2 = 411.3519
    doc_l2 = 343.9045
    ticket_score = l2_to_match_score(ticket_l2)
    doc_score = l2_to_match_score(doc_l2)
    assert ticket_l2 > doc_l2
    assert ticket_score < doc_score
    assert 0.0 <= ticket_score <= 100.0
    assert 0.0 <= doc_score <= 100.0
