from __future__ import annotations

import pytest

from app.services.dangerous_content_v6_rc5_fusion import (
    DANGEROUS_ACTION,
    DANGEROUS_CATEGORY,
    PACKAGED_EVIDENCE_DIRECTORY,
    analyze_dangerous_content_v6_rc5_for_fusion,
    apply_dangerous_content_v6_rc5_fusion,
    get_dangerous_content_v6_rc5_readiness,
)


def baseline(category: str = "Normal/Ignore") -> dict[str, object]:
    return {
        "category": category,
        "severity": "None" if category == "Normal/Ignore" else "High",
        "action": "Allow" if category == "Normal/Ignore" else "Existing action",
        "confidence": 0.70,
        "human_review_required": category != "Normal/Ignore",
        "reason": "Existing decision.",
        "matched_signals": [],
    }


def proposal() -> dict[str, object]:
    return {
        "available": True,
        "fusion_status": "review_only_candidate_found",
        "proposed_category": DANGEROUS_CATEGORY,
        "proposed_action": DANGEROUS_ACTION,
        "proposed_severity": "High",
        "confidence": 0.82,
        "human_review_required": True,
        "proposal_source": "frozen_rc4_path_applied",
        "automatic_enforcement_allowed": False,
    }


def apply(category: str = "Normal/Ignore", analysis=None):
    return apply_dangerous_content_v6_rc5_fusion(
        **baseline(category),
        analysis=proposal() if analysis is None else analysis,
    )


def test_frozen_candidate_has_passing_guarded_verdict():
    readiness = get_dangerous_content_v6_rc5_readiness()
    assert readiness["ready"] is True
    assert readiness["automatic_enforcement_allowed"] is False


def test_portable_readiness_evidence_is_packaged():
    assert (PACKAGED_EVIDENCE_DIRECTORY / "manifest.json").is_file()
    assert (
        PACKAGED_EVIDENCE_DIRECTORY / "independent_evaluation_verdict.json"
    ).is_file()


def test_normal_boundary_can_become_review_only_dangerous():
    result = apply()
    assert result["category"] == DANGEROUS_CATEGORY
    assert result["action"] == DANGEROUS_ACTION
    assert result["human_review_required"] is True
    assert result["decision_applied"] is True
    assert result["automatic_enforcement_allowed"] is False


def test_uncertain_boundary_can_become_review_only_dangerous():
    result = apply("Uncertain")
    assert result["category"] == DANGEROUS_CATEGORY
    assert result["decision_applied"] is True
    assert result["automatic_enforcement_allowed"] is False


def test_existing_dangerous_owner_is_not_rewritten():
    result = apply(DANGEROUS_CATEGORY)
    assert result["category"] == DANGEROUS_CATEGORY
    assert result["action"] == "Existing action"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "dangerous_content_owner_already_applied"


@pytest.mark.parametrize(
    "owner",
    [
        "Violent Content",
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Identity Theft & Impersonation",
        "Cyberbullying & Harassment",
        "Hate Speech & Discrimination",
        "Religiously Offensive Content",
        "Terrorism & Extremism",
        "Child Exploitation",
        "Misinformation & Fake News",
    ],
)
def test_established_category_owners_cannot_be_overridden(owner: str):
    result = apply(owner)
    assert result["category"] == owner
    assert result["action"] == "Existing action"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_established_category_owner"


def test_no_proposal_cannot_create_allow_or_dangerous_override():
    analysis = {
        "available": True,
        "fusion_status": "no_dangerous_boundary_override",
        "proposed_category": "",
        "confidence": 0.0,
        "automatic_enforcement_allowed": False,
    }
    result = apply(analysis=analysis)
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"
    assert result["decision_applied"] is False


def test_non_textual_input_cannot_create_proposal():
    analysis = analyze_dangerous_content_v6_rc5_for_fusion(
        "A dangerous act is promoted to viewers.",
        ["visual_description"],
    )
    assert analysis["fusion_status"] == "non_textual_input_no_override"
    assert analysis["proposed_category"] == ""
    assert analysis["automatic_enforcement_allowed"] is False


def test_third_person_violent_depiction_cannot_become_dangerous_content():
    analysis = analyze_dangerous_content_v6_rc5_for_fusion(
        "The video graphically depicts a person being stabbed.",
        ["text"],
    )
    assert analysis["fusion_status"] == "blocked_by_violent_depiction_boundary"
    assert analysis["proposed_category"] == ""
    assert analysis["human_review_required"] is False
    assert analysis["automatic_enforcement_allowed"] is False
