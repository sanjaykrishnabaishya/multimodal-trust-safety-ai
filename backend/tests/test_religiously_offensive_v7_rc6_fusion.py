from __future__ import annotations

import pytest

from app.services.religiously_offensive_v7_rc6_fusion import (
    REQUIRED_ACTION,
    apply_religiously_offensive_v7_rc6_fusion,
)
from app.services.religiously_offensive_v7_rc6_service import (
    get_religiously_offensive_v7_rc6_status,
)


def base_result(category: str = "Normal/Ignore") -> dict:
    return {
        "category": category,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.70,
        "human_review_required": False,
        "reason": "Baseline result.",
        "matched_signals": [],
    }


def accepted_analysis(path: str = "semantic_and_anchor") -> dict:
    return {
        "available": True,
        "decision": "religiously_offensive_review_only",
        "decision_path": path,
        "primary_category": "Religiously Offensive Content",
        "confidence": 0.82,
        "action": REQUIRED_ACTION,
        "human_review_required": True,
        "automatic_enforcement_allowed": False,
        "policy_veto_applied": False,
        "reason": "Validated direct sacred-target attack.",
    }


def apply(category: str, analysis: dict, safe: bool = False) -> dict:
    return apply_religiously_offensive_v7_rc6_fusion(
        **base_result(category),
        analysis=analysis,
        safe_context_confirmed=safe,
    )


def test_frozen_candidate_has_passing_verdict() -> None:
    status = get_religiously_offensive_v7_rc6_status()
    assert status["available"] is True
    assert status["independently_validated"] is True
    assert status["eligible_for_guarded_live_integration"] is True
    assert status["automatic_enforcement_allowed"] is False


@pytest.mark.parametrize("starting_category", ["Normal/Ignore", "Uncertain", "Abusive Words"])
def test_allowed_boundary_can_become_review_only_religious(
    starting_category: str,
) -> None:
    result = apply(starting_category, accepted_analysis())
    assert result["category"] == "Religiously Offensive Content"
    assert result["action"] == REQUIRED_ACTION
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False
    assert result["decision_applied"] is True


@pytest.mark.parametrize(
    "protected_category",
    [
        "Hate Speech & Discrimination",
        "Cyberbullying & Harassment",
        "Violent Content",
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Child Exploitation",
    ],
)
def test_established_category_owners_cannot_be_overridden(
    protected_category: str,
) -> None:
    result = apply(protected_category, accepted_analysis("direct_advocacy_and_anchor"))
    assert result["category"] == protected_category
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_category_isolation"


def test_policy_veto_cannot_create_religious_override() -> None:
    analysis = accepted_analysis()
    analysis.update(
        {
            "decision": "no_religious_boundary_override",
            "primary_category": "",
            "policy_veto_applied": True,
            "policy_veto_reason": "reported_or_documented_context",
        }
    )
    result = apply("Normal/Ignore", analysis)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "reported_or_documented_context"


def test_fusion_safe_context_blocks_override() -> None:
    result = apply("Normal/Ignore", accepted_analysis(), safe=True)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_fusion_safe_context"


def test_unavailable_specialist_fails_without_change() -> None:
    result = apply(
        "Normal/Ignore",
        {"available": False, "decision": "not_applied"},
    )
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "unavailable"
