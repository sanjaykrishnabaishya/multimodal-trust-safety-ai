from __future__ import annotations

from app.services.cyberbullying_depiction_boundary_service import (
    analyze_cyberbullying_depiction_boundary,
    apply_graphic_depiction_review_boundary,
)
from app.services.cyberbullying_rc2_service import (
    apply_cyberbullying_rc2_fusion,
)


def targeted_analysis() -> dict[str, object]:
    return {
        "available": True,
        "decision": "accepted_supporting_evidence",
        "primary_category": "Cyberbullying & Harassment",
        "predicted_label": "targeted_threat",
        "model_score": 0.91,
        "reason": "Model proposed targeted intimidation.",
        "automatic_enforcement_allowed": False,
    }


def baseline() -> dict[str, object]:
    return {
        "category": "Normal/Ignore",
        "severity": "None",
        "action": "Allow",
        "confidence": 0.70,
        "human_review_required": False,
        "reason": "Existing decision.",
        "matched_signals": [],
    }


def test_third_person_graphic_depiction_gets_cyber_veto():
    result = analyze_cyberbullying_depiction_boundary(
        "The video graphically depicts a person being stabbed."
    )
    assert result["confirmed_third_person_depiction"] is True
    assert result["cyberbullying_targeted_threat_veto_allowed"] is True


def test_direct_address_threat_does_not_get_veto():
    result = analyze_cyberbullying_depiction_boundary(
        "The video shows a man saying: I will stab you; watch your back."
    )
    assert result["confirmed_third_person_depiction"] is False


def test_repeated_targeting_does_not_get_veto():
    result = analyze_cyberbullying_depiction_boundary(
        "The footage shows a person being beaten while the sender repeatedly "
        "messages an identified target every day."
    )
    assert result["confirmed_third_person_depiction"] is False


def test_confirmed_depiction_blocks_only_fusion_override():
    result = apply_cyberbullying_rc2_fusion(
        **baseline(),
        analysis=targeted_analysis(),
        safe_context_confirmed=True,
    )
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_confirmed_safe_context"


def test_confirmed_depiction_fails_closed_to_human_review():
    analysis = analyze_cyberbullying_depiction_boundary(
        "The video graphically depicts a person being stabbed."
    )
    result = apply_graphic_depiction_review_boundary(
        **baseline(),
        analysis=analysis,
    )
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["decision_applied"] is True
    assert result["automatic_enforcement_allowed"] is False


def test_depiction_review_boundary_preserves_existing_owner():
    analysis = analyze_cyberbullying_depiction_boundary(
        "The video graphically depicts a person being stabbed."
    )
    values = baseline()
    values.update(
        {
            "category": "Publishing Private Information",
            "severity": "High",
            "action": "Existing action",
            "human_review_required": True,
        }
    )
    result = apply_graphic_depiction_review_boundary(
        **values,
        analysis=analysis,
    )
    assert result["category"] == "Publishing Private Information"
    assert result["action"] == "Existing action"
    assert result["decision_applied"] is False
    assert result["boundary_status"] == "blocked_by_established_category_owner"
