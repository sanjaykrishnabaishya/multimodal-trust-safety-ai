from __future__ import annotations

import pytest

from app.services.illegal_activities_v2_rc2_service import (
    ILLEGAL_ACTION,
    ILLEGAL_CATEGORY,
    analyze_illegal_activities_v2_rc2,
    apply_illegal_activities_v2_rc2_fusion,
)


def baseline(category: str = "Normal/Ignore", action: str | None = None) -> dict:
    return {
        "category": category,
        "severity": "None" if category == "Normal/Ignore" else "High",
        "action": action or ("Allow" if category == "Normal/Ignore" else "Existing action"),
        "confidence": 0.70,
        "human_review_required": category != "Normal/Ignore",
        "reason": "Existing decision.",
        "matched_signals": [],
    }


def apply(category: str, analysis: dict, action: str | None = None) -> dict:
    return apply_illegal_activities_v2_rc2_fusion(
        **baseline(category, action),
        analysis=analysis,
    )


@pytest.mark.parametrize(
    "text",
    [
        "A supplier offers controlled substances with courier delivery after payment.",
        "Payment is required before the account provides access to a forged passport.",
        "Available to buyers is illegal betting; direct message the seller.",
        "A commercial listing promotes the sale of a fake government emblem.",
    ],
)
def test_fresh_transaction_word_order_is_review_only_illegal(text: str) -> None:
    analysis = analyze_illegal_activities_v2_rc2(
        text,
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert result["category"] == ILLEGAL_CATEGORY
    assert result["action"] == ILLEGAL_ACTION
    assert result["human_review_required"] is True
    assert result["automatic_enforcement_allowed"] is False


@pytest.mark.parametrize(
    "text",
    [
        "A fictional scene mentions illegal drugs; it is fictional and not real.",
        "A research paper quotes 'buy now' beside an unlicensed firearm, quoted for analysis.",
        "A historical archive preserves a quoted advertisement for illegal betting; it is not a live offer.",
        "A prevention campaign discusses counterfeit currency and contains no transaction.",
    ],
)
def test_explicit_safe_boundaries_do_not_create_override(text: str) -> None:
    analysis = analyze_illegal_activities_v2_rc2(
        text,
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert analysis["fusion_status"] == "safe_context_no_override"
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"


def test_legitimate_context_does_not_create_override() -> None:
    analysis = analyze_illegal_activities_v2_rc2(
        "A museum exhibition contains a film prop described as a prohibited weapon.",
        ["text"],
        use_openrouter=False,
    )
    assert analysis["fusion_status"] == "legitimate_context_no_override"
    assert analysis["proposed_category"] == ""


def test_unknown_licensing_routes_to_uncertain_review() -> None:
    analysis = analyze_illegal_activities_v2_rc2(
        "A page mentions unlicensed gambling; license status is unclear and no transaction is established.",
        ["text"],
        use_openrouter=False,
    )
    result = apply("Normal/Ignore", analysis)
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True


@pytest.mark.parametrize(
    "owner,action",
    [
        ("Child Exploitation", "Block and immediately escalate"),
        ("Terrorism & Extremism", "Block and escalate"),
        ("Spam, Scam & Phishing", "Block, warn, or limit distribution"),
        ("Publishing Private Information", "Remove exposed information and send for human review"),
        ("Graphic, Obscene & Sexual Content", "Age-restrict or limit distribution"),
        ("Dangerous Content", "Remove and send for human review"),
    ],
)
def test_established_owner_is_preserved_exactly(owner: str, action: str) -> None:
    analysis = analyze_illegal_activities_v2_rc2(
        "A seller offers illegal drugs with delivery available.",
        ["text"],
        use_openrouter=False,
    )
    result = apply(owner, analysis, action)
    assert result["category"] == owner
    assert result["action"] == action
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_established_category_owner"


def test_child_risk_never_reaches_external_advisory(monkeypatch) -> None:
    called = False

    def external(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        "app.services.illegal_activities_v2_rc2_service."
        "analyze_illegal_activities_with_openrouter",
        external,
    )
    analysis = analyze_illegal_activities_v2_rc2(
        "A minor child is linked to a sexual private image.",
        ["text"],
    )
    assert called is False
    assert analysis["fusion_status"] == "blocked_by_child_safety_boundary"
    assert analysis["proposed_category"] == ""


def test_non_text_input_cannot_call_external_advisory(monkeypatch) -> None:
    called = False

    def external(*args, **kwargs):
        nonlocal called
        called = True
        return {}

    monkeypatch.setattr(
        "app.services.illegal_activities_v2_rc2_service."
        "analyze_illegal_activities_with_openrouter",
        external,
    )
    analyze_illegal_activities_v2_rc2(
        "A seller offers illegal drugs with delivery available.",
        ["visual_description"],
    )
    assert called is False
