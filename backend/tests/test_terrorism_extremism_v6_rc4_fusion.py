from __future__ import annotations

import pytest

from app.services.terrorism_extremism_service import (
    NORMAL_CATEGORY,
    TERRORISM_CATEGORY,
    UNCERTAIN_CATEGORY,
)
from app.services.terrorism_extremism_v6_rc4_fusion import (
    PACKAGED_EVIDENCE_DIRECTORY,
    analyze_terrorism_extremism_v6_rc4_for_fusion,
    apply_terrorism_extremism_v6_rc4_fusion,
    get_terrorism_extremism_v6_rc4_readiness,
)


def baseline(category: str = NORMAL_CATEGORY) -> dict[str, object]:
    return {
        "category": category,
        "severity": "None" if category == NORMAL_CATEGORY else "High",
        "action": "Allow" if category == NORMAL_CATEGORY else "Existing action",
        "confidence": 0.70,
        "human_review_required": category != NORMAL_CATEGORY,
        "reason": "Existing decision.",
        "matched_signals": [],
    }


def apply(text: str, category: str = NORMAL_CATEGORY, sources=None):
    if sources is None:
        sources = ["text"]
    analysis = analyze_terrorism_extremism_v6_rc4_for_fusion(text, sources)
    return analysis, apply_terrorism_extremism_v6_rc4_fusion(
        **baseline(category), analysis=analysis
    )


def test_frozen_candidate_has_passing_guarded_verdict():
    readiness = get_terrorism_extremism_v6_rc4_readiness()
    assert readiness["ready"] is True
    assert readiness["automatic_enforcement_allowed"] is False


def test_portable_readiness_evidence_is_packaged():
    assert (PACKAGED_EVIDENCE_DIRECTORY / "manifest.json").is_file()
    assert (
        PACKAGED_EVIDENCE_DIRECTORY
        / "independent_evaluation_verdict.json"
    ).is_file()


def test_claimed_designation_and_behavior_is_review_only_terrorism():
    analysis, result = apply(
        "A designated terrorist organization requests contributions."
    )
    assert result["category"] == TERRORISM_CATEGORY
    assert result["action"] == "Block and escalate"
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False
    assert analysis["community_candidate_confirmed_designation"] is False


def test_wikidata_candidate_and_behavior_is_uncertain_only():
    analysis, result = apply("A message encourages people to join Al-Qaeda.")
    assert analysis["community_candidate_used"] is True
    assert result["category"] == UNCERTAIN_CATEGORY
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False


def test_neutral_candidate_mention_does_not_override():
    _, result = apply("A library index contains the name Al-Qaeda.")
    assert result["category"] == NORMAL_CATEGORY
    assert result["decision_applied"] is False


def test_safe_reporting_does_not_override():
    _, result = apply(
        "A university report about Al-Qaeda condemns recruitment."
    )
    assert result["category"] == NORMAL_CATEGORY
    assert result["decision_applied"] is False


def test_legitimate_recruitment_does_not_override():
    _, result = apply(
        "Microsoft encourages registration for a cloud engineering workshop."
    )
    assert result["category"] == NORMAL_CATEGORY
    assert result["decision_applied"] is False


@pytest.mark.parametrize(
    "owner",
    [
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Identity Theft & Impersonation",
        "Cyberbullying & Harassment",
        "Hate Speech & Discrimination",
        "Religiously Offensive Content",
        "Violent Content",
        "Child Exploitation",
    ],
)
def test_established_category_owners_cannot_be_overridden(owner: str):
    _, result = apply(
        "A designated terrorist organization requests contributions.",
        category=owner,
    )
    assert result["category"] == owner
    assert result["action"] == "Existing action"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_established_category_owner"


def test_visual_only_input_cannot_create_override():
    analysis, result = apply(
        "A designated terrorist organization requests contributions.",
        sources=["visual_description"],
    )
    assert analysis["fusion_status"] == "non_textual_input_no_override"
    assert result["category"] == NORMAL_CATEGORY
    assert result["decision_applied"] is False
