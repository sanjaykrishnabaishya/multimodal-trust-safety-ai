from app.services.multimodal_capability_gate_service import (
    apply_violent_content_readiness_gate,
)


def violent_decision() -> dict:
    return {
        "category": "Violent Content",
        "severity": "Low",
        "action": "Allow with sensitive-content warning",
        "confidence": 0.82,
        "human_review_required": False,
        "reason": "Violence appears in contextual material.",
        "matched_signals": ["violent_content_specialist"],
        "decision_sources": ["violent_content_specialist"],
    }


def test_failed_candidate_cannot_automatically_allow() -> None:
    result, warnings = apply_violent_content_readiness_gate(
        decision=violent_decision()
    )
    assert result["category"] == "Violent Content"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["confidence"] <= 0.75
    assert result["automatic_enforcement_allowed"] is False
    assert warnings


def test_failed_candidate_cannot_automatically_enforce() -> None:
    decision = violent_decision()
    decision["action"] = "Block immediately"
    decision["severity"] = "High"
    decision["human_review_required"] = True
    result, _ = apply_violent_content_readiness_gate(decision=decision)
    assert result["action"] == "Refer to human review"
    assert result["recommended_action_before_readiness_gate"] == "Block immediately"


def test_other_categories_are_unchanged() -> None:
    decision = violent_decision()
    decision["category"] = "Cyberbullying & Harassment"
    original = dict(decision)
    result, warnings = apply_violent_content_readiness_gate(decision=decision)
    assert result == original
    assert warnings == []
