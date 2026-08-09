from app.services.multimodal_capability_gate_service import (
    apply_multimodal_capability_gate,
)


def base_decision(category: str = "Normal/Ignore") -> dict:
    return {
        "category": category,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.7,
        "human_review_required": False,
        "reason": "No signal detected.",
        "matched_signals": [],
        "decision_sources": ["rule_engine"],
    }


def test_safe_image_is_not_automatically_confirmed() -> None:
    result, warnings = apply_multimodal_capability_gate(
        decision=base_decision(),
        content_type="image",
    )
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["confidence"] <= 0.5
    assert result["visual_safety_gate_applied"] is True
    assert warnings


def test_safe_video_is_not_automatically_confirmed() -> None:
    result, _ = apply_multimodal_capability_gate(
        decision=base_decision(),
        content_type="video",
    )
    assert result["category"] == "Uncertain"
    assert result["human_review_required"] is True


def test_text_result_is_unchanged() -> None:
    original = base_decision()
    result, warnings = apply_multimodal_capability_gate(
        decision=original,
        content_type="text",
    )
    assert result == original
    assert warnings == []


def test_detected_violation_is_not_overwritten() -> None:
    original = base_decision("Spam, Scam & Phishing")
    original["action"] = "Block and warn"
    original["human_review_required"] = True
    result, warnings = apply_multimodal_capability_gate(
        decision=original,
        content_type="image",
    )
    assert result == original
    assert warnings == []
