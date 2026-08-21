from __future__ import annotations

import pytest

from app.services.illegal_activities_v1_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    analyze_illegal_activities_v1,
    apply_illegal_activities_v1_fusion,
)


def baseline(category="Normal/Ignore"):
    return {
        "category": category,
        "severity": "None" if category == "Normal/Ignore" else "High",
        "action": "Allow" if category == "Normal/Ignore" else "Existing action",
        "confidence": 0.70,
        "human_review_required": category != "Normal/Ignore",
        "reason": "Existing decision.",
        "matched_signals": [],
    }


def apply(category, analysis):
    return apply_illegal_activities_v1_fusion(
        **baseline(category),
        analysis=analysis,
    )


def test_transaction_evidence_is_review_only_illegal_candidate():
    analysis = analyze_illegal_activities_v1(
        "Illegal drugs are for sale. Contact me to order now.",
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert result["category"] == ILLEGAL_CATEGORY
    assert result["action"] == ILLEGAL_ACTION
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False


def test_safe_reporting_does_not_create_illegal_override():
    analysis = analyze_illegal_activities_v1(
        "A news report about illegal drugs warns viewers not to buy them.",
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert analysis["fusion_status"] == "safe_reporting_or_prevention_no_override"
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"


def test_legitimate_microsoft_recruitment_is_not_illegal_activity():
    analysis = analyze_illegal_activities_v1(
        "Microsoft job recruitment is open for software engineers.",
        ["text"],
        use_openrouter=False,
    )
    assert analysis["proposed_category"] == ""
    assert analysis["automatic_enforcement_allowed"] is False


def test_jurisdiction_uncertainty_routes_to_review():
    analysis = analyze_illegal_activities_v1(
        "A post mentions an online betting service with unknown licensing.",
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True


@pytest.mark.parametrize(
    "owner",
    [
        "Child Exploitation",
        "Terrorism & Extremism",
        "Malicious Programs",
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Identity Theft & Impersonation",
        "Graphic, Obscene & Sexual Content",
        "Dangerous Content",
    ],
)
def test_established_category_owner_cannot_be_overridden(owner):
    analysis = analyze_illegal_activities_v1(
        "Illegal drugs are for sale. Contact me to order now.",
        ["text"],
        use_openrouter=False,
    )
    result = apply(owner, analysis)
    assert result["category"] == owner
    assert result["action"] == "Existing action"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_established_category_owner"


def test_child_safety_language_is_never_sent_to_illegal_route():
    analysis = analyze_illegal_activities_v1(
        "A minor child was targeted for a sexual private image.",
        ["text"],
        use_openrouter=False,
    )
    assert analysis["fusion_status"] == "blocked_by_child_safety_boundary"
    assert analysis["proposed_category"] == ""
    assert analysis["openrouter"]["used"] is False


def test_visual_description_alone_cannot_call_external_advisory(monkeypatch):
    called = False

    def external(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        "app.services.illegal_activities_v1_service."
        "analyze_illegal_activities_with_openrouter",
        external,
    )
    analyze_illegal_activities_v1(
        "Illegal drugs are for sale. Contact me to order now.",
        ["visual_description"],
    )
    assert called is False
