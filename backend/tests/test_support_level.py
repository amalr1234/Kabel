import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from app.retrieve import build_where, filter_fallbacks
from app.support_level import classify_support_level, normalize_level


def test_classify_l1_password_unlock():
    level, reason = classify_support_level(
        title="User locked after password reset",
        description="Cannot login, account locked in SU01",
        category="authentication",
        transactions="SU01",
        resolution_time_hours=0.5,
    )
    assert level == "L1"
    assert "L1" in reason


def test_classify_l2_authorization():
    level, reason = classify_support_level(
        title="Missing authorization object",
        description="SU53 shows missing object for finance app",
        category="authorization",
        transactions="SU53",
        resolution_time_hours=3.0,
    )
    assert level == "L2"
    assert "L2" in reason


def test_classify_l3_performance():
    level, reason = classify_support_level(
        title="HANA high memory",
        description="Expensive SQL and ST03N dumps during peak load",
        category="performance",
        transactions="ST03N",
        sap_notes="2345678",
        resolution_time_hours=7.0,
    )
    assert level == "L3"
    assert "L3" in reason


def test_normalize_level():
    assert normalize_level("l2") == "L2"
    assert normalize_level("critical") is None


def test_filter_fallbacks_include_support_level():
    where = build_where("SAP", "authorization", None, "resolved", "L2")
    assert {"support_level": {"$eq": "L2"}} in where["$and"]
    variants = filter_fallbacks("SAP", "authorization", None, "L2", prefer_resolved=True)
    assert variants[0]["$and"][-1] == {"status": {"$eq": "resolved"}} or any(
        clause.get("support_level") == {"$eq": "L2"}
        for clause in variants[0]["$and"]
    )
    assert variants[-1] is None
