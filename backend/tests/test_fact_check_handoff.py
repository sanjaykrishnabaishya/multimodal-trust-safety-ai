"""Offline handoff contracts; not independent truth/accuracy evaluation."""
from copy import deepcopy

import pytest

from app.services import fact_check_fusion_service as service


def evidence_result():
    return {
        "available": True,
        "evidence_status": "SUPPORTS",
        "confidence": 0.9,
        "evidence_conflict_detected": False,
        "evidence": [{"source_name": "Fixture source",
                      "source_url": "https://example.org/evidence",
                      "alignment_passed": True}],
    }


def run(monkeypatch, payload):
    monkeypatch.setattr(service, "should_run_fact_check", lambda **kw: (True, "fixture"))
    monkeypatch.setattr(service, "analyze_fact_check", lambda text: payload)
    return service.analyze_fact_check_for_fusion("A fixture claim.", service.NORMAL_CATEGORY)


@pytest.mark.parametrize("patch", [
    {"confidence": None}, {"confidence": "bad"}, {"confidence": float("nan")},
    {"confidence": float("inf")}, {"confidence": -1}, {"confidence": 2},
    {"confidence": True}, {"evidence": []}, {"evidence": None},
    {"evidence": [None]}, {"available": False}, {"available": "true"},
    {"evidence_conflict_detected": True}, {"evidence_conflict_detected": None},
    {"evidence_status": "SOMETHING_ELSE"},
])
def test_invalid_handoff_requires_review(monkeypatch, patch):
    result = run(monkeypatch, {**evidence_result(), **patch})
    assert result["category"] == "Uncertain"
    assert result["human_review_required"] is True
    assert result["confidence"] == 0
    assert result["automatic_enforcement_allowed"] is False


@pytest.mark.parametrize("patch", [
    {"source_url": "file:///private.txt"}, {"source_url": "https://[bad"},
    {"source_url": "https://user:secret@example.org"}, {"source_url": "https:///"},
    {"source_name": ""}, {"alignment_passed": False}, {"alignment_passed": "true"},
])
def test_unattributable_or_unaligned_evidence(monkeypatch, patch):
    payload = deepcopy(evidence_result())
    payload["evidence"][0].update(patch)
    assert run(monkeypatch, payload)["category"] == "Uncertain"


@pytest.mark.parametrize("payload", [None, [], "SUPPORTS"])
def test_wrong_response_type(monkeypatch, payload):
    assert run(monkeypatch, payload)["category"] == "Uncertain"


@pytest.mark.parametrize("status,category,review", [
    ("SUPPORTS", service.NORMAL_CATEGORY, False),
    ("REFUTES", service.MISINFORMATION_CATEGORY, True),
    ("NOT_ENOUGH_INFO", "Uncertain", True),
])
def test_valid_routes(monkeypatch, status, category, review):
    result = run(monkeypatch, {**evidence_result(), "evidence_status": status})
    assert result["category"] == category
    assert result["human_review_required"] is review
    assert result["automatic_enforcement_allowed"] is False
    assert result["confidence"] <= 0.8


def test_provider_failure_is_private_and_reviewed(monkeypatch):
    monkeypatch.setattr(service, "should_run_fact_check", lambda **kw: (True, "fixture"))
    def fail(text):
        raise RuntimeError("PRIVATE_PROVIDER_DETAIL")
    monkeypatch.setattr(service, "analyze_fact_check", fail)
    result = service.analyze_fact_check_for_fusion("A claim.", service.NORMAL_CATEGORY)
    assert result["category"] == "Uncertain"
    assert "PRIVATE_PROVIDER_DETAIL" not in str(result)


def test_other_category_never_calls_provider(monkeypatch):
    def fail(text):
        pytest.fail("Other category must retain priority")
    monkeypatch.setattr(service, "analyze_fact_check", fail)
    result = service.analyze_fact_check_for_fusion("The moon is made of cheese.", "Violent Content")
    assert result["decision_override_allowed"] is False
    assert result["fact_check_analysis_used"] is False
