from __future__ import annotations

from app.services.cyberbullying_rc2_service import (
    apply_cyberbullying_rc2_fusion,
    get_cyberbullying_rc2_status,
)


def analysis(
    decision: str,
    label: str,
    category: str,
    score: float = 0.90,
) -> dict:
    return {
        "available": True,
        "decision": decision,
        "predicted_label": label,
        "primary_category": category,
        "model_score": score,
        "reason": "Controlled RC2 test evidence.",
    }


def apply(
    current_category: str,
    candidate: dict,
    safe_context_confirmed: bool = False,
) -> dict:
    return apply_cyberbullying_rc2_fusion(
        category=current_category,
        severity="None",
        action="Allow",
        confidence=0.70,
        human_review_required=False,
        reason="Baseline decision.",
        matched_signals=[],
        analysis=candidate,
        safe_context_confirmed=safe_context_confirmed,
    )


def test_frozen_candidate_has_passing_verdict() -> None:
    status = get_cyberbullying_rc2_status()
    assert status["available"] is True
    assert status["independently_validated"] is True
    assert status["automatic_enforcement_allowed"] is False


def test_targeted_threat_is_review_only_cyberbullying() -> None:
    result = apply(
        "Normal/Ignore",
        analysis(
            "accepted_supporting_evidence",
            "targeted_threat",
            "Cyberbullying & Harassment",
        ),
    )
    assert result["category"] == "Cyberbullying & Harassment"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["decision_applied"] is True


def test_single_abuse_stays_abusive_words_and_review_only() -> None:
    result = apply(
        "Normal/Ignore",
        analysis(
            "accepted_supporting_evidence",
            "abusive_words",
            "Abusive Words",
        ),
    )
    assert result["category"] == "Abusive Words"
    assert result["action"] == "Mask abusive terms and refer to human review"
    assert result["human_review_required"] is True


def test_abusive_words_do_not_replace_cyberbullying_primary() -> None:
    result = apply(
        "Cyberbullying & Harassment",
        analysis(
            "accepted_supporting_evidence",
            "abusive_words",
            "Abusive Words",
        ),
    )
    assert result["category"] == "Cyberbullying & Harassment"
    assert result["human_review_required"] is True


def test_unrelated_categories_cannot_be_overridden() -> None:
    candidate = analysis(
        "accepted_supporting_evidence",
        "targeted_threat",
        "Cyberbullying & Harassment",
    )
    protected = (
        "Hate Speech & Discrimination",
        "Sexual Harassment",
        "Publishing Private Information",
        "Spam, Scam & Phishing",
        "Child Exploitation",
        "Misinformation & Fake News",
    )
    for category in protected:
        result = apply(category, candidate)
        assert result["category"] == category
        assert result["decision_applied"] is False
        assert result["fusion_status"] == "blocked_by_category_isolation"


def test_safe_signal_never_creates_allow_override() -> None:
    result = apply(
        "Spam, Scam & Phishing",
        analysis("no_boundary_override", "safe_or_other", ""),
    )
    assert result["category"] == "Spam, Scam & Phishing"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "safe_signal_no_override"


def test_uncertain_normal_content_is_referred_for_review() -> None:
    result = apply(
        "Normal/Ignore",
        analysis("uncertain", "targeted_threat", "Uncertain", 0.30),
    )
    assert result["category"] == "Uncertain"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True


def test_uncertain_result_does_not_replace_existing_category() -> None:
    result = apply(
        "Spam, Scam & Phishing",
        analysis("uncertain", "abusive_words", "Uncertain", 0.40),
    )
    assert result["category"] == "Spam, Scam & Phishing"
    assert result["decision_applied"] is False


def test_confirmed_safe_context_blocks_uncertain_override() -> None:
    result = apply(
        "Normal/Ignore",
        analysis("uncertain", "abusive_words", "Uncertain", 0.40),
        safe_context_confirmed=True,
    )
    assert result["category"] == "Normal/Ignore"
    assert result["action"] == "Allow"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_confirmed_safe_context"


def test_rc2_cannot_replace_confirmed_graphic_violence() -> None:
    result = apply(
        "Violent Content",
        analysis(
            "accepted_supporting_evidence",
            "targeted_threat",
            "Cyberbullying & Harassment",
        ),
    )
    assert result["category"] == "Violent Content"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_category_isolation"
