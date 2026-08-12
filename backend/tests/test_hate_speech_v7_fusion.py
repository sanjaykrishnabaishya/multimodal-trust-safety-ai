from app.services.hate_speech_v7_service import apply_hate_speech_v7_fusion


def baseline(category="Normal/Ignore"):
    return {
        "category": category,
        "severity": "None",
        "action": "Allow",
        "confidence": 0.70,
        "human_review_required": False,
        "reason": "Baseline decision.",
        "matched_signals": [],
    }


def accepted(*, protected=True):
    return {
        "available": True,
        "decision": "accepted_review_only",
        "primary_category": "Hate Speech & Discrimination",
        "model_score": 0.91,
        "protected_reference_detected": protected,
        "reporting_or_counterspeech_detected": False,
        "reason": "Validated Hate Speech evidence requires review.",
        "automatic_enforcement_allowed": False,
    }


def apply(category="Normal/Ignore", analysis=None, safe=False):
    return apply_hate_speech_v7_fusion(
        **baseline(category),
        analysis=analysis or accepted(),
        safe_context_confirmed=safe,
    )


def test_normal_can_become_review_only_hate_speech():
    result = apply()
    assert result["category"] == "Hate Speech & Discrimination"
    assert result["action"] == "Refer to human review"
    assert result["human_review_required"] is True
    assert result["decision_applied"] is True


def test_abusive_words_need_explicit_protected_reference():
    result = apply("Abusive Words", accepted(protected=False))
    assert result["category"] == "Abusive Words"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "abusive_words_retained_without_protected_target"


def test_protected_group_hate_can_refine_abusive_words():
    result = apply("Abusive Words", accepted(protected=True))
    assert result["category"] == "Hate Speech & Discrimination"
    assert result["human_review_required"] is True


def test_cyberbullying_cannot_be_overridden():
    result = apply("Cyberbullying & Harassment")
    assert result["category"] == "Cyberbullying & Harassment"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_category_isolation"


def test_unrelated_categories_cannot_be_overridden():
    for category in (
        "Violent Content",
        "Spam, Scam & Phishing",
        "Publishing Private Information",
        "Misinformation & Fake News",
        "Religiously Offensive Content",
    ):
        result = apply(category)
        assert result["category"] == category
        assert result["decision_applied"] is False


def test_safe_context_blocks_hate_override():
    result = apply(safe=True)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
    assert result["fusion_status"] == "blocked_by_safe_context"


def test_below_threshold_never_creates_allow_or_hate_override():
    analysis = accepted()
    analysis["decision"] = "below_selective_threshold_no_override"
    result = apply(analysis=analysis)
    assert result["category"] == "Normal/Ignore"
    assert result["decision_applied"] is False
